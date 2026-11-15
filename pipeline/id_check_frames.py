"""Required deliverable: ID-check frames every 30 min on each camera.

Usage:  python code/id_check_frames.py
Reads:  out/ids_<cam>.parquet if it exists (boxes with cow_id), else out/tracks_cam.parquet (no IDs yet)
Writes: out/id_check/<cam>/<Day>_<HHMM>.jpg   (2000 px wide, boxes + cow IDs + time stamp)
        out/id_check/index.csv                 (which frame was used for each 30-min slot)
"""
import os, glob, subprocess
import numpy as np, pandas as pd, cv2

W = 2000
CAMS = {"Cam 01": "cam01", "Cam 02": "cam02", "Cam 03": "cam03"}
clip_path = {os.path.basename(l.strip()): l.strip() for l in open("clips.txt") if l.strip()}
tracks = None
palette = [(66, 135, 245), (245, 66, 66), (66, 245, 96), (245, 200, 66), (200, 66, 245),
           (66, 245, 230), (245, 130, 66), (150, 245, 66), (245, 66, 170), (255, 255, 255)]


def load(cam, tag):
    global tracks
    f = f"out/ids_{tag}.parquet"
    if os.path.exists(f):
        return pd.read_parquet(f), True
    if tracks is None:
        tracks = pd.read_parquet("out/tracks_cam.parquet")
    g = tracks[tracks.cam == cam].copy(); g["cow_id"] = "?"; g["id_conf"] = np.nan
    return g, False


def grab(path, t):
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-c:v", "hevc", "-ss", f"{t:.3f}", "-i", path,
           "-frames:v", "1", "-vf", f"scale={W}:-2", "-f", "image2pipe", "-vcodec", "png", "-"]
    buf = subprocess.run(cmd, capture_output=True).stdout
    return cv2.imdecode(np.frombuffer(buf, np.uint8), cv2.IMREAD_COLOR) if buf else None


rows = []
for cam, tag in CAMS.items():
    g, has_ids = load(cam, tag)
    os.makedirs(f"out/id_check/{tag}", exist_ok=True)
    frames = g.groupby("ts").first()[["clip", "t_sec", "day", "frame_w"]].sort_index()
    for day in sorted(g.day.unique()):
        fd = frames[frames.day == day]
        if fd.empty: continue
        d0 = fd.index.min().normalize()
        for slot in pd.date_range(d0, d0 + pd.Timedelta(hours=23, minutes=30), freq="30min"):
            # nearest frame with boxes within +/- 5 min of the slot
            i = fd.index.get_indexer([slot], method="nearest")[0]
            ts = fd.index[i]
            if abs((ts - slot).total_seconds()) > 300:
                rows.append(dict(cam=cam, day=day, slot=slot, used_ts=None, n_boxes=0, note="no cows detected near this time")); continue
            r = fd.iloc[i]
            img = grab(clip_path[r.clip], r.t_sec)
            if img is None:
                rows.append(dict(cam=cam, day=day, slot=slot, used_ts=ts, n_boxes=0, note="decode failed")); continue
            s = W / r.frame_w
            b = g[g.ts == ts]
            for x in b.itertuples():
                k = int(x.cow_id[1:]) - 1 if x.cow_id.startswith("C") else 9
                col = palette[k % len(palette)] if x.cow_id.startswith("C") else (180, 180, 180)
                p1, p2 = (int(x.x1 * s), int(x.y1 * s)), (int(x.x2 * s), int(x.y2 * s))
                cv2.rectangle(img, p1, p2, col, 4)
                lab = x.cow_id if np.isnan(x.id_conf) else f"{x.cow_id} {x.id_conf:.2f}"
                cv2.putText(img, lab, (p1[0], max(35, p1[1] - 10)), cv2.FONT_HERSHEY_SIMPLEX, 1.3, (0, 0, 0), 7)
                cv2.putText(img, lab, (p1[0], max(35, p1[1] - 10)), cv2.FONT_HERSHEY_SIMPLEX, 1.3, col, 3)
            hdr = f"{cam} | {day} | slot {slot:%H:%M} | frame {ts:%H:%M:%S} | {len(b)} cows | {'IDs' if has_ids else 'no IDs yet'}"
            cv2.rectangle(img, (0, 0), (W, 60), (0, 0, 0), -1)
            cv2.putText(img, hdr, (15, 42), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 2)
            out = f"out/id_check/{tag}/{day.replace(' ', '')}_{slot:%H%M}.jpg"
            cv2.imwrite(out, img, [cv2.IMWRITE_JPEG_QUALITY, 80])
            rows.append(dict(cam=cam, day=day, slot=slot, used_ts=ts, n_boxes=len(b), note=out))
    print(cam, "done", flush=True)
pd.DataFrame(rows).to_csv("out/id_check/index.csv", index=False)
print("saved", len(rows), "slots -> out/id_check/")
