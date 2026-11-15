"""Keyframe detection pass for the BRD hackathon.
Usage: python detect.py clips.txt START COUNT OUTDIR
For each clip: decode HEVC keyframes (every ~2 s), resize to 2000 px wide,
run YOLO on animal classes, write one parquet per clip (resumable).
"""
import sys, os, re, glob, json, subprocess, tempfile, time
from datetime import datetime, timedelta
import pandas as pd
import torch
from ultralytics import YOLO

lst, start, count, outdir = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
clips = [l.strip() for l in open(lst) if l.strip()][start:start + count]
os.makedirs(outdir, exist_ok=True)

WEIGHTS = os.environ.get("YOLO_W", "yolo11m.pt")
IMGSZ = int(os.environ.get("IMGSZ", "1280"))
CONF = float(os.environ.get("CONF", "0.15"))
W = 2000                          # decode width (keeps cows big enough, cuts IO)
ANIMALS = list(range(14, 24))     # COCO bird..giraffe; black cows at night may be called horse/bear/etc.
BATCH = 32
tmp_root = os.environ.get("TMPDIR", "/tmp")

print(f"torch {torch.__version__} cuda={torch.cuda.is_available()} "
      f"gpu={torch.cuda.get_device_name(0) if torch.cuda.is_available() else '-'}", flush=True)
model = YOLO(WEIGHTS)
use_half = torch.cuda.is_available()

def probe(clip):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                          "-show_entries", "stream=width,height,time_base,r_frame_rate",
                          "-of", "json", clip], capture_output=True, text=True).stdout
    s = json.loads(out)["streams"][0]
    num, den = s["time_base"].split("/")
    fn, fd = s["r_frame_rate"].split("/")
    return int(s["width"]), int(s["height"]), int(num) / int(den), int(fn) / int(fd)

for k, clip in enumerate(clips):
    name = os.path.basename(clip)
    out = os.path.join(outdir, os.path.splitext(name)[0] + ".parquet")
    if os.path.exists(out):
        continue
    t_start = time.time()
    m = re.search(r"Event(\d{14})(\d{3})", name)
    clip_start = datetime.strptime(m.group(1), "%Y%m%d%H%M%S")
    cam_code = m.group(2)
    parts = clip.split(os.sep)
    day, cam = parts[-3], parts[-2]
    try:
        ow, oh, tb, fps = probe(clip)
    except Exception as e:
        print(f"[skip] probe failed {name}: {e}", flush=True); continue
    scale = ow / W
    rows = []
    with tempfile.TemporaryDirectory(dir=tmp_root) as td:
        cmd = ["ffmpeg", "-v", "error", "-c:v", "hevc", "-skip_frame", "nokey", "-i", clip,
               "-vsync", "0", "-frame_pts", "1", "-vf", f"scale={W}:-2", "-q:v", "3",
               os.path.join(td, "%09d.jpg")]
        subprocess.run(cmd, check=False)
        frames = sorted(glob.glob(os.path.join(td, "*.jpg")))
        for i in range(0, len(frames), BATCH):
            batch = frames[i:i + BATCH]
            res = model.predict(batch, imgsz=IMGSZ, conf=CONF, classes=ANIMALS,
                                verbose=False, half=use_half)
            for f, r in zip(batch, res):
                pts = int(os.path.basename(f)[:-4])
                t_sec = round(pts * tb, 3)
                base = dict(day=day, cam=cam, cam_code=cam_code, clip=name,
                            clip_start=clip_start, pts=pts, t_sec=t_sec,
                            ts=clip_start + timedelta(seconds=t_sec), frame_w=ow, frame_h=oh)
                b = r.boxes
                if b is None or len(b) == 0:
                    rows.append({**base, "cls": -1, "conf": 0.0, "x1": None, "y1": None, "x2": None, "y2": None})
                    continue
                xyxy = (b.xyxy.cpu().numpy() * scale).round(1)
                for (x1, y1, x2, y2), c, cf in zip(xyxy, b.cls.cpu().numpy(), b.conf.cpu().numpy()):
                    rows.append({**base, "cls": int(c), "conf": round(float(cf), 4),
                                 "x1": x1, "y1": y1, "x2": x2, "y2": y2})
    df = pd.DataFrame(rows)
    df.to_parquet(out + ".tmp", index=False)
    os.replace(out + ".tmp", out)
    nf = df["pts"].nunique() if len(df) else 0
    nd = int((df["cls"] >= 0).sum()) if len(df) else 0
    print(f"[{k+1}/{len(clips)}] {day}/{cam}/{name}: frames={nf} dets={nd} "
          f"tb={tb:.5f} {time.time()-t_start:.1f}s", flush=True)
print("DONE", flush=True)
