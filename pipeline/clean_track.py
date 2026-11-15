"""Step 10+11: clean detections and link them into per-camera tracks.

Usage:  python code/clean_track.py            (reads out/det/*.parquet)
Output: out/tracks_cam.parquet   one row per kept box, with track_id
        out/track_summary.csv    quick stats per day/camera

What it does, per camera and day, in time order (keyframes ~2 s apart):
  1. keep animal classes that black Angus get called (cow/horse/sheep/bear/dog), conf >= CONF
  2. class-agnostic NMS per frame (same cow boxed twice as cow+horse -> one box)
  3. drop boxes that are too small (far-away cows in other pens)
  4. if ground_truth/zones.json has a 'pen' polygon for this camera, keep only
     boxes whose foot point (bottom-centre) is inside it
  5. link boxes across consecutive frames with Hungarian matching on
     (1 - IoU) + centre distance; a track ends after MAX_MISS missed frames
"""
import os, glob, json, sys
import numpy as np, pandas as pd
from scipy.optimize import linear_sum_assignment

CONF = float(os.environ.get("CONF", "0.25"))
KEEP_CLS = {16, 17, 18, 19, 21}          # dog, horse, sheep, cow, bear
NMS_IOU = 0.6
MIN_AREA_FRAC = float(os.environ.get("MIN_AREA_FRAC", "0.0008"))  # of full frame
MAX_MISS = 5                              # keyframes (~10 s) before a track ends
GATE = 1.2                                # max cost to accept a match
ZONES = "ground_truth/zones.json"
CAM_KEY = {"Cam 01": "cam01", "Cam 02": "cam02", "Cam 03": "cam03"}


def iou_matrix(a, b):
    """a: (n,4) b: (m,4) xyxy -> (n,m) IoU"""
    if len(a) == 0 or len(b) == 0:
        return np.zeros((len(a), len(b)))
    x1 = np.maximum(a[:, None, 0], b[None, :, 0]); y1 = np.maximum(a[:, None, 1], b[None, :, 1])
    x2 = np.minimum(a[:, None, 2], b[None, :, 2]); y2 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    aa = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1]); ab = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    return inter / (aa[:, None] + ab[None, :] - inter + 1e-9)


def nms(boxes, scores, thr):
    order = np.argsort(-scores); keep = []
    while len(order):
        i = order[0]; keep.append(i)
        if len(order) == 1: break
        ious = iou_matrix(boxes[i:i + 1], boxes[order[1:]])[0]
        order = order[1:][ious < thr]
    return keep


def point_in_poly(x, y, poly):
    """vectorised ray casting; x,y arrays; poly list of [u,v]"""
    poly = np.asarray(poly, float); inside = np.zeros(len(x), bool); j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]; xj, yj = poly[j]
        cross = ((yi > y) != (yj > y)) & (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi)
        inside ^= cross; j = i
    return inside


def load_pens():
    if not os.path.exists(ZONES):
        print("no zones.json yet -> pen filter OFF"); return {}
    z = json.load(open(ZONES)); pens = {}
    for k, v in z.items():
        if isinstance(v, dict) and "pen" in v:
            pens[k.lower().replace(" ", "")] = v["pen"]
    print("pen polygons for:", list(pens) or "none")
    return pens


def clean(df, pens, det_scale=1.0):
    df = df[(df.cls.isin(KEEP_CLS)) & (df.conf >= CONF)].copy()
    area = (df.x2 - df.x1) * (df.y2 - df.y1)
    df = df[area >= MIN_AREA_FRAC * df.frame_w * df.frame_h]
    out = []
    for _, g in df.groupby(["cam", "pts", "clip"], sort=False):
        b = g[["x1", "y1", "x2", "y2"]].to_numpy(float)
        out.append(g.iloc[nms(b, g.conf.to_numpy(), NMS_IOU)])
    df = pd.concat(out) if out else df.iloc[:0]
    df["foot_u"] = (df.x1 + df.x2) / 2; df["foot_v"] = df.y2
    df["in_pen"] = True
    for cam, key in CAM_KEY.items():
        if key in pens:
            m = df.cam == cam
            df.loc[m, "in_pen"] = point_in_poly(df.loc[m, "foot_u"].to_numpy(),
                                                df.loc[m, "foot_v"].to_numpy(), pens[key])
    return df


def track(g, prefix):
    """g: one camera+day, sorted by ts. Returns g with track_id."""
    g = g.sort_values("ts").reset_index(drop=True)
    tid = np.full(len(g), -1, int); next_id = 0
    active = {}   # id -> (box, last_frame_idx)
    frames = list(g.groupby("ts", sort=True).indices.items())
    diag = np.hypot(g.frame_w.iloc[0], g.frame_h.iloc[0])
    for fi, (ts, idx) in enumerate(frames):
        boxes = g.loc[idx, ["x1", "y1", "x2", "y2"]].to_numpy(float)
        ids = [k for k, (b, last) in active.items() if fi - last <= MAX_MISS]
        if ids and len(boxes):
            tb = np.array([active[k][0] for k in ids])
            iou = iou_matrix(tb, boxes)
            ct = (tb[:, :2] + tb[:, 2:]) / 2; cb = (boxes[:, :2] + boxes[:, 2:]) / 2
            dist = np.linalg.norm(ct[:, None] - cb[None], axis=2) / (0.15 * diag)
            cost = (1 - iou) + dist
            r, c = linear_sum_assignment(cost)
            used = set()
            for i, j in zip(r, c):
                if cost[i, j] <= GATE:
                    tid[idx[j]] = ids[i]; active[ids[i]] = (boxes[j], fi); used.add(j)
        for j in range(len(boxes)):
            if tid[idx[j]] == -1:
                tid[idx[j]] = next_id; active[next_id] = (boxes[j], fi); next_id += 1
        active = {k: v for k, v in active.items() if fi - v[1] <= MAX_MISS}
    g["track_id"] = [f"{prefix}_{t:05d}" for t in tid]
    return g


def main():
    files = sorted(glob.glob("out/det/*.parquet"))
    print(f"{len(files)} detection files"); sys.stdout.flush()
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    frames_all = df.groupby(["day", "cam"]).apply(lambda g: g[["clip", "pts"]].drop_duplicates().shape[0])
    pens = load_pens()
    df = clean(df, pens)
    df = df[df.in_pen]
    parts, rows = [], []
    for (day, cam), g in df.groupby(["day", "cam"]):
        prefix = f"{day.replace(' ', '').lower()}_{CAM_KEY[cam]}"
        t = track(g, prefix); parts.append(t)
        per_frame = t.groupby("ts").size()
        dur = t.groupby("track_id").ts.agg(lambda s: (s.max() - s.min()).total_seconds())
        rows.append(dict(day=day, cam=cam, frames=int(frames_all.get((day, cam), 0)),
                         frames_with_cows=len(per_frame),
                         cows_per_frame_median=float(per_frame.median()),
                         cows_per_frame_p90=float(per_frame.quantile(0.9)),
                         tracks=t.track_id.nunique(),
                         track_median_s=float(dur.median()), track_p90_s=float(dur.quantile(0.9))))
        print(rows[-1]); sys.stdout.flush()
    out = pd.concat(parts, ignore_index=True)
    cols = ["day", "cam", "clip", "ts", "t_sec", "pts", "track_id", "x1", "y1", "x2", "y2",
            "foot_u", "foot_v", "conf", "cls", "frame_w", "frame_h"]
    out[cols].to_parquet("out/tracks_cam.parquet", index=False)
    pd.DataFrame(rows).to_csv("out/track_summary.csv", index=False)
    print("saved out/tracks_cam.parquet rows=", len(out))


if __name__ == "__main__":
    main()
