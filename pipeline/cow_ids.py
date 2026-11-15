"""Step 12a: closed-set ID tracker -> exactly 10 cow IDs (C01-C10) on the main camera.

Usage:  python code/cow_ids.py [CAM]          (default CAM="Cam 03", the whole-pen view)
Input:  out/tracks_cam.parquet (pen-filtered)
Output: out/ids_<cam>.parquet   every box of that camera + cow_id, id_cost, id_conf, id_source
        out/id_events_<cam>.csv  moments where two cows were close enough to swap (for the agent to check)

Idea: we KNOW there are 10 cows and nobody enters or leaves. So instead of starting new
tracks, every frame we match the boxes to 10 persistent cow "slots" (Hungarian assignment).
 - stage 1: match boxes to cows near their last position (strict gate)
 - stage 2: a cow missing for a while may re-appear anywhere (loose gate)
 - a cow with no box keeps its last position (hidden / occluded)
The recording runs straight through midnight, so Day 1 and Day 2 are one continuous sequence
and IDs carry over between days.
"""
import sys, os
import numpy as np, pandas as pd
from scipy.optimize import linear_sum_assignment

CAM = sys.argv[1] if len(sys.argv) > 1 else "Cam 03"
K = 10
STRICT = 1.5        # max cost to continue a cow from its last position
LOOSE = 6.0         # max cost to re-acquire a cow that has been missing >= REACQ frames
REACQ = 15          # keyframes (~30 s)
CLOSE = 0.8         # cows closer than this (in box-height units) can swap -> event


def box_cost(cow_box, boxes):
    """distance between foot points in units of box height (perspective-safe) + (1 - IoU)"""
    cf = np.array([(cow_box[0] + cow_box[2]) / 2, cow_box[3]])
    bf = np.stack([(boxes[:, 0] + boxes[:, 2]) / 2, boxes[:, 3]], 1)
    h = np.maximum((cow_box[3] - cow_box[1] + boxes[:, 3] - boxes[:, 1]) / 2, 1.0)
    d = np.linalg.norm(bf - cf, axis=1) / h
    x1 = np.maximum(cow_box[0], boxes[:, 0]); y1 = np.maximum(cow_box[1], boxes[:, 1])
    x2 = np.minimum(cow_box[2], boxes[:, 2]); y2 = np.minimum(cow_box[3], boxes[:, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    ua = (cow_box[2] - cow_box[0]) * (cow_box[3] - cow_box[1]) + (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1]) - inter
    return d + (1 - inter / np.maximum(ua, 1e-9))


def run(g):
    g = g.sort_values(["ts", "x1"]).reset_index(drop=True)
    cow_box = [None] * K; miss = np.zeros(K, int)
    cid = np.full(len(g), -1); cost_out = np.full(len(g), np.nan)
    events = []
    for ts, idx in g.groupby("ts", sort=True).indices.items():
        boxes = g.loc[idx, ["x1", "y1", "x2", "y2"]].to_numpy(float)
        n = len(boxes)
        # initialise empty slots (start of video, or fewer than 10 seen so far): left-to-right
        if any(b is None for b in cow_box):
            free = [k for k in range(K) if cow_box[k] is None]
            if all(b is None for b in cow_box):
                order = np.argsort((boxes[:, 0] + boxes[:, 2]) / 2)
                for k, j in zip(free, order):
                    cow_box[k] = boxes[j]; cid[idx[j]] = k; cost_out[idx[j]] = 0.0
                miss[:] = 0
                continue
        known = [k for k in range(K) if cow_box[k] is not None]
        C = np.full((len(known), n), 1e6)
        for r, k in enumerate(known):
            C[r] = box_cost(cow_box[k], boxes)
        assigned_det, assigned_cow = set(), set()
        # stage 1: strict continuation
        rr, cc = linear_sum_assignment(C)
        for r, c in zip(rr, cc):
            if C[r, c] <= STRICT:
                k = known[r]; cid[idx[c]] = k; cost_out[idx[c]] = C[r, c]
                assigned_det.add(c); assigned_cow.add(k)
        # stage 2: re-acquire long-missing cows / fill empty slots with leftover boxes
        left_d = [j for j in range(n) if j not in assigned_det]
        cand = [k for k in range(K) if k not in assigned_cow and (cow_box[k] is None or miss[k] >= REACQ)]
        if left_d and cand:
            C2 = np.full((len(cand), len(left_d)), 1e6)
            for r, k in enumerate(cand):
                C2[r] = 0.0 if cow_box[k] is None else box_cost(cow_box[k], boxes[left_d])
            rr, cc = linear_sum_assignment(C2)
            for r, c in zip(rr, cc):
                if C2[r, c] <= LOOSE:
                    k = cand[r]; j = left_d[c]; cid[idx[j]] = k; cost_out[idx[j]] = C2[r, c] + STRICT
                    assigned_cow.add(k)
        # update state
        for j in range(n):
            k = cid[idx[j]]
            if k >= 0:
                cow_box[k] = boxes[j]
        for k in range(K):
            miss[k] = 0 if k in assigned_cow else miss[k] + 1
        # swap-risk events: two matched cows whose foot points are very close
        m = [(idx[j], cid[idx[j]]) for j in range(n) if cid[idx[j]] >= 0]
        for a in range(len(m)):
            for b in range(a + 1, len(m)):
                ba, bb = boxes[list(idx).index(m[a][0])], boxes[list(idx).index(m[b][0])]
                if box_cost(ba, bb[None])[0] < CLOSE:
                    events.append(dict(ts=ts, cow_a=f"C{m[a][1]+1:02d}", cow_b=f"C{m[b][1]+1:02d}"))
    g["cow_id"] = np.where(cid >= 0, [f"C{k+1:02d}" for k in np.clip(cid, 0, None)], "UNK")
    g["id_cost"] = cost_out
    g["id_conf"] = np.where(cid >= 0, np.clip(1 - np.nan_to_num(cost_out, nan=9) / (STRICT + LOOSE), 0, 1), 0.0).round(3)
    g["id_source"] = np.where((cid >= 0) & (cost_out <= STRICT), "observed_continuous",
                              np.where(cid >= 0, "reacquired_estimated", "unassigned"))
    return g, pd.DataFrame(events)


def main():
    df = pd.read_parquet("out/tracks_cam.parquet")
    g = df[df.cam == CAM]
    print(f"{CAM}: {len(g)} boxes, {g.ts.nunique()} frames"); sys.stdout.flush()
    out, ev = run(g)
    tag = CAM.replace(" ", "").lower()
    out.to_parquet(f"out/ids_{tag}.parquet", index=False)
    if len(ev):
        ev = ev.sort_values("ts")
        # collapse consecutive frames of the same pair into one event
        ev["gap"] = ev.groupby(["cow_a", "cow_b"]).ts.diff().dt.total_seconds().fillna(1e9)
        ev["event"] = (ev.gap > 10).cumsum()
        ev = ev.groupby(["event", "cow_a", "cow_b"]).ts.agg(["min", "max", "size"]).reset_index()
        ev.columns = ["event", "cow_a", "cow_b", "start", "end", "frames"]
    ev.to_csv(f"out/id_events_{tag}.csv", index=False)
    s = out.cow_id.value_counts()
    print("boxes per cow_id:\n", s.to_string())
    print("id_source:\n", out.id_source.value_counts(normalize=True).round(3).to_string())
    per = out[out.cow_id != "UNK"].groupby("ts").cow_id.nunique()
    print(f"cows identified per frame: median {per.median():.0f}, p10 {per.quantile(.1):.0f}")
    print(f"swap-risk events: {len(ev)}")
    print("saved", f"out/ids_{tag}.parquet")


if __name__ == "__main__":
    main()
