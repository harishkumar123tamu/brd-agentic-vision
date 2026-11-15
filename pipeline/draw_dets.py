"""Draw detections from one clip's parquet onto 4 keyframes -> out/viz/<clip>.jpg
Usage: python code/draw_dets.py out/det/Event20261107000417006.parquet [MIN_CONF]
Colour: green = cow (19), orange = other animal class, label = class:conf
"""
import sys, os, glob, subprocess, tempfile
import pandas as pd, numpy as np, cv2

pq = sys.argv[1]
min_conf = float(sys.argv[2]) if len(sys.argv) > 2 else 0.15
df = pd.read_parquet(pq)
clip_name = df["clip"].iloc[0]
clip = [l.strip() for l in open("clips.txt") if l.strip().endswith(clip_name)][0]
W = 2000
NAMES = {14: "bird", 15: "cat", 16: "dog", 17: "horse", 18: "sheep", 19: "cow",
         20: "elephant", 21: "bear", 22: "zebra", 23: "giraffe"}

with tempfile.TemporaryDirectory() as td:
    subprocess.run(["ffmpeg", "-v", "error", "-c:v", "hevc", "-skip_frame", "nokey", "-i", clip,
                    "-vsync", "0", "-frame_pts", "1", "-vf", f"scale={W}:-2", "-q:v", "3",
                    os.path.join(td, "%09d.jpg")], check=False)
    frames = sorted(glob.glob(os.path.join(td, "*.jpg")))
    picks = [frames[i] for i in np.linspace(0, len(frames) - 1, 4).astype(int)]
    tiles = []
    for f in picks:
        pts = int(os.path.basename(f)[:-4])
        img = cv2.imread(f)
        scale = df["frame_w"].iloc[0] / W
        d = df[(df.pts == pts) & (df.cls >= 0) & (df.conf >= min_conf)]
        for r in d.itertuples():
            x1, y1, x2, y2 = [int(v / scale) for v in (r.x1, r.y1, r.x2, r.y2)]
            col = (0, 220, 0) if r.cls == 19 else (0, 140, 255)
            cv2.rectangle(img, (x1, y1), (x2, y2), col, 4)
            cv2.putText(img, f"{NAMES.get(r.cls, r.cls)}:{r.conf:.2f}", (x1, max(30, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.1, col, 3)
        t = d["t_sec"].iloc[0] if len(d) else pts / 30
        cv2.putText(img, f"{clip_name}  t={t:.0f}s  n={len(d)}", (20, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 0, 255), 4)
        tiles.append(cv2.resize(img, (1000, int(img.shape[0] * 1000 / img.shape[1]))))
    h = min(t.shape[0] for t in tiles)
    tiles = [t[:h] for t in tiles]
    grid = np.vstack([np.hstack(tiles[:2]), np.hstack(tiles[2:])])
    os.makedirs("out/viz", exist_ok=True)
    out = f"out/viz/{os.path.splitext(clip_name)[0]}.jpg"
    cv2.imwrite(out, grid, [cv2.IMWRITE_JPEG_QUALITY, 80])
    print("saved", out)
