"""Step 12b: give Cam 01 / Cam 02 boxes the Cam 03 cow IDs, at the feed bunk.

Usage:  python code/link_bunk.py
Reads:  out/ids_cam03.parquet, out/tracks_cam.parquet, ground_truth/zones.json
Writes: out/ids_cam01.parquet, out/ids_cam02.parquet  (cow_id for boxes at the bunk, UNK elsewhere)
        out/link_summary.csv

Why at the bunk: the pen map shows Front cam 1 (Cam 01) and Front cam 2 (Cam 02) at the bunk and the
Back cam (Cam 03) at the far corner. Cows at the bunk stand in one row, so their west->east order is the
same in every camera. We put every bunk cow on a 0..1 "bunk coordinate" (0 = west/chute end, 1 = east end)
and match cameras frame by frame (nearest Cam 03 frame within 2 s) with the Hungarian algorithm.
Cam 03 looks from the back, so its left-to-right is east->west (mirrored).
Cam 02 sees only the east part of the bunk: assumed to cover bunk coordinate 0.35-1.0 (estimate).
"""
import json
import numpy as np, pandas as pd
from scipy.optimize import linear_sum_assignment

Z = json.load(open("ground_truth/zones.json"))
GATE = 0.22          # max difference in bunk coordinate
DT = 2.0             # max seconds between the camera frames being matched
CAM02_RANGE = (0.35, 1.0)


def near_poly(u, v, poly, margin):
    """foot point inside polygon OR within `margin` px of it (approx: test inflated bounding region)"""
    import cv2
    P = np.asarray(poly, np.float32).reshape(-1, 1, 2)
    return np.array([cv2.pointPolygonTest(P, (float(a), float(b)), True) >= -margin for a, b in zip(u, v)])


def bunk_coord(cam, g):
    xc = ((g.x1 + g.x2) / 2).to_numpy()
    xs = np.array(Z[cam]["feed_bunk"])[:, 0]
    if cam == "cam03":            # mirrored: image left = east
        return (xs.max() - xc) / (xs.max() - xs.min())
    if cam == "cam01":
        return xc / g.frame_w.to_numpy()
    lo, hi = CAM02_RANGE         # cam02: east part of bunk only
    return lo + (hi - lo) * xc / g.frame_w.to_numpy()


def at_bunk(cam, g):
    poly = Z[cam]["feed_bunk"]
    margin = {"cam03": 160, "cam01": 250, "cam02": 300}[cam]
    # head/body reaches the bunk: use bottom-centre for cam03 (far view), box centre for the front cams
    u = ((g.x1 + g.x2) / 2).to_numpy()
    v = (g.y2 if cam == "cam03" else (g.y1 + g.y2) / 2).to_numpy()
    return near_poly(u, v, poly, margin)


ids3 = pd.read_parquet("out/ids_cam03.parquet")
b3 = ids3[(ids3.cow_id != "UNK")].copy()
b3 = b3[at_bunk("cam03", b3)]
b3["s"] = bunk_coord("cam03", b3)
f3 = {ts: g for ts, g in b3.groupby("ts")}
t3 = np.array(sorted(f3), dtype="datetime64[ns]")
print("cam03 bunk boxes:", len(b3), "frames with cows at bunk:", len(f3), flush=True)

tracks = pd.read_parquet("out/tracks_cam.parquet")
rows = []
for cam_name, cam in [("Cam 01", "cam01"), ("Cam 02", "cam02")]:
    g = tracks[tracks.cam == cam_name].copy().reset_index(drop=True)
    g["at_bunk"] = at_bunk(cam, g)
    g["s"] = np.nan; g.loc[g.at_bunk, "s"] = bunk_coord(cam, g[g.at_bunk])
    g["cow_id"] = "UNK"; g["link_cost"] = np.nan; g["link_dt"] = np.nan
    n_frames = n_linked = 0
    for ts, idx in g[g.at_bunk].groupby("ts").groups.items():
        n_frames += 1
        k = np.searchsorted(t3, np.datetime64(ts))
        cands = [c for c in (k - 1, k) if 0 <= c < len(t3)]
        if not cands: continue
        c = min(cands, key=lambda c: abs((t3[c] - np.datetime64(ts)) / np.timedelta64(1, "s")))
        dt = abs((t3[c] - np.datetime64(ts)) / np.timedelta64(1, "s"))
        if dt > DT: continue
        ref = f3[pd.Timestamp(t3[c])]
        s1 = g.loc[idx, "s"].to_numpy(); s3 = ref.s.to_numpy()
        C = np.abs(s1[:, None] - s3[None, :])
        r, cc = linear_sum_assignment(C)
        for i, j in zip(r, cc):
            if C[i, j] <= GATE:
                ii = idx[i]
                g.at[ii, "cow_id"] = ref.cow_id.iloc[j]; g.at[ii, "link_cost"] = C[i, j]; g.at[ii, "link_dt"] = dt
                n_linked += 1
    g["id_source"] = np.where(g.cow_id != "UNK", "linked_from_cam03_at_bunk", "not_linked")
    g["id_conf"] = np.where(g.cow_id != "UNK", (1 - g.link_cost.fillna(1) / GATE).clip(0, 1).round(3), 0.0)
    g.drop(columns=["s"]).to_parquet(f"out/ids_{cam}.parquet", index=False)
    rows.append(dict(cam=cam_name, boxes=len(g), boxes_at_bunk=int(g.at_bunk.sum()),
                     bunk_frames=n_frames, boxes_linked=n_linked,
                     share_bunk_boxes_linked=round(n_linked / max(1, g.at_bunk.sum()), 3)))
    print(rows[-1], flush=True)
pd.DataFrame(rows).to_csv("out/link_summary.csv", index=False)
print("saved out/ids_cam01.parquet, out/ids_cam02.parquet")
