"""Level 2 evidence: cut short H.264 clips for the top-3 risk cows -> out/clips/*.mp4 + out/clips/index.csv

Usage:  python code/evidence_clips.py [N_TOP=3]
For each top cow (from out/brd_risk.csv), on Day 2:
  1. longest lying bout                      (Cam 03, whole pen)
  2. herd feeding (>=4 others) but she isn't  (Cam 03)
  3. one of her own feeding moments           (Cam 02 bunk close-up if she was identified there, else Cam 01/03)
Each clip: 15 s, 1280 px wide, her box drawn (box from the detection nearest the clip middle).
"""
import os, sys, re, subprocess
from datetime import datetime, timedelta
import numpy as np, pandas as pd

N_TOP = int(sys.argv[1]) if len(sys.argv) > 1 else 3
LEN = 15
CODE = {"cam03": "003", "cam01": "006", "cam02": "017"}
os.makedirs("out/clips", exist_ok=True)

clips = [l.strip() for l in open("clips.txt") if l.strip()]
cat = []
for p in clips:
    m = re.search(r"Event(\d{14})(\d{3})", os.path.basename(p))
    cat.append((p, datetime.strptime(m.group(1), "%Y%m%d%H%M%S"), m.group(2)))
cat = pd.DataFrame(cat, columns=["path", "start", "code"]).sort_values("start")

risk = pd.read_csv("out/brd_risk.csv").sort_values("rank").head(N_TOP)
am = pd.read_csv("out/activity_minutes.csv", parse_dates=["minute"])
am = am[am.day == "Day 2"]
ids = {c: pd.read_parquet(f"out/ids_{c}.parquet") for c in ("cam03", "cam01", "cam02") if os.path.exists(f"out/ids_{c}.parquet")}


def find_clip(cam, t):
    c = cat[(cat.code == CODE[cam]) & (cat.start <= t)]
    if c.empty: return None, None
    r = c.iloc[-1]
    off = (t - r.start).total_seconds()
    return (r.path, off) if off < 300 - 2 else (None, None)


def box_at(cam, cow, t):
    g = ids[cam]; g = g[(g.cow_id == cow)]
    if g.empty: return None
    i = (g.ts - t).abs().idxmin()
    if abs((g.at[i, "ts"] - t).total_seconds()) > 30: return None
    r = g.loc[i]; return r.x1, r.y1, r.x2, r.y2, r.frame_w


def cut(cam, cow, t, tag, desc):
    path, off = find_clip(cam, t)
    if path is None: return None
    out = f"out/clips/{cow}_{tag}_{cam}_{t:%m%d_%H%M}.mp4"
    vf = "scale=1280:-2"
    b = box_at(cam, cow, t + timedelta(seconds=LEN / 2))
    if b:
        s = 1280 / b[4]
        x, y, w, h = int(b[0] * s), int(b[1] * s), int((b[2] - b[0]) * s), int((b[3] - b[1]) * s)
        vf += f",drawbox=x={x}:y={y}:w={w}:h={h}:color=red@0.9:t=4"
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-y", "-c:v", "hevc", "-ss", f"{max(0, off):.1f}", "-i", path,
           "-t", str(LEN), "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-an", out]
    subprocess.run(cmd)
    if not os.path.exists(out): return None
    return dict(cow_id=cow, clip=out, camera=cam, time=t, kind=tag, description=desc, box_drawn=bool(b))


rows = []
herd_feed = am[am.behavior == "feeding"].groupby("minute").cow_id.nunique()
for cow in risk.cow_id:
    a = am[am.cow_id == cow].sort_values("minute")
    # 1. longest lying bout
    ly = a.behavior.eq("lying"); grp = (ly != ly.shift()).cumsum()
    bouts = a[ly].groupby(grp[ly]).minute.agg(["min", "max", "size"]).sort_values("size", ascending=False)
    if len(bouts):
        b = bouts.iloc[0]; t = b["min"] + timedelta(minutes=min(5, int(b["size"]) // 2))
        r = cut("cam03", cow, t, "lying", f"Longest Day-2 lying bout: {int(b['size'])} min from {b['min']:%H:%M}")
        if r: rows.append(r)
    # 2. herd feeding, she is not at the bunk
    not_feed = a[(a.behavior.isin(["lying", "standing"])) & (a.n_obs > 0)].set_index("minute")
    cand = herd_feed[(herd_feed >= 4)].index.intersection(not_feed.index)
    if len(cand):
        t = cand[len(cand) // 2]
        r = cut("cam03", cow, t, "missed_feeding",
                f"{int(herd_feed[t])} herd-mates feeding at {t:%H:%M} while {cow} is {not_feed.at[t, 'behavior']}")
        if r: rows.append(r)
    # 3. her own feeding moment (bunk close-up preferred)
    fm = a[a.behavior == "feeding"]
    if len(fm):
        for cam in ("cam02", "cam01", "cam03"):
            if cam in ids:
                g = ids[cam]; g = g[(g.cow_id == cow) & g.ts.dt.floor("min").isin(fm.minute)]
                if len(g):
                    t = g.ts.iloc[len(g) // 2] - timedelta(seconds=LEN / 2)
                    r = cut(cam, cow, t, "feeding_closeup", f"{cow} at the bunk ({cam}); check ears, nose, head carriage")
                    if r: rows.append(r); break
    print(cow, "clips:", sum(1 for x in rows if x["cow_id"] == cow), flush=True)

pd.DataFrame(rows).to_csv("out/clips/index.csv", index=False)
print(pd.DataFrame(rows)[["cow_id", "kind", "camera", "time", "clip"]].to_string(index=False))
