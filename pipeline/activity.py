"""Step 13: rule-based behavior for every cow and every minute -> activity.csv, time budgets, minute features.

Usage:  python code/activity.py
Reads:  out/ids_cam03.parquet (cow IDs, whole-pen view), out/ids_cam01.parquet + out/ids_cam02.parquet
        (cows identified at the bunk), ground_truth/zones.json
Writes: out/activity.csv          one row per behavior bout (cow_id, day, start_time, end_time, behavior, camera,
                                  confidence, evidence, method)
        out/activity_minutes.csv  one row per cow per minute (all 2 x 1440 minutes)
        out/time_budget.csv       minutes per behavior per cow per day
        out/minute_features.parquet   per cow-minute signals for Level 2 (bunk, lying, motion, isolation, visibility)

Rules per keyframe (every ~2 s), then majority over the minute:
  at bunk     : Cam 03 foot point at the feed-bunk zone, OR the cow is identified at the bunk by Cam 01/02
  at waterer  : Cam 03 foot point at the waterer zone
  moving      : foot point moved > 0.25 box-heights since the previous keyframe (<= 4 s earlier)
  lying       : box height < 0.68 x typical standing height at that image row (perspective-corrected)
Minute label priority: feeding > drinking > walking > lying > standing; no observation -> other_not_visible.
Rumination, grooming and social interaction need jaw/head detail -> left to the VLM/agent stage
(this file marks them as not determined by rules).
"""
import json
import numpy as np, pandas as pd, cv2

Z = json.load(open("ground_truth/zones.json"))
LIE_RATIO = 0.68
MOVE_THR = 0.25
BUNK_M, WATER_M = 160, 120   # px margins around zones (full-res Cam 03)


def near(poly, u, v, margin):
    P = np.asarray(poly, np.float32).reshape(-1, 1, 2)
    return np.array([cv2.pointPolygonTest(P, (float(a), float(b)), True) >= -margin for a, b in zip(u, v)])


d = pd.read_parquet("out/ids_cam03.parquet")
d = d[d.cow_id != "UNK"].copy()
# keep only the 2 recording days (last clips spill a few seconds past midnight into a 3rd date)
_cnt = d.groupby(d.ts.dt.normalize()).size()
DAYS = sorted(_cnt[_cnt > 0.2 * _cnt.max()].index)
d = d[d.ts.dt.normalize().isin(DAYS)].copy()
print("recording days:", [str(x.date()) for x in DAYS], flush=True)
d["h"] = d.y2 - d.y1; d["w"] = d.x2 - d.x1
d["foot_u"] = (d.x1 + d.x2) / 2; d["foot_v"] = d.y2

# perspective-corrected "standing height": 85th percentile of box height per 100-px band of foot_v, smoothed
d["band"] = (d.foot_v // 100).astype(int)
ref = d.groupby("band").h.quantile(0.85).rolling(3, center=True, min_periods=1).median()
d["h_ref"] = d.band.map(ref)
d["lying"] = d.h < LIE_RATIO * d.h_ref
d["bunk3"] = near(Z["cam03"]["feed_bunk"], d.foot_u, d.foot_v, BUNK_M)
d["water"] = near(Z["cam03"]["waterer"], d.foot_u, d.foot_v, WATER_M) if "waterer" in Z["cam03"] else False

# motion per cow between consecutive keyframes
d = d.sort_values(["cow_id", "ts"])
du = d.groupby("cow_id").foot_u.diff(); dv = d.groupby("cow_id").foot_v.diff()
dt = d.groupby("cow_id").ts.diff().dt.total_seconds()
d["move"] = (np.hypot(du, dv) / d.h.clip(lower=1)).where(dt <= 4)
d["moving"] = d.move > MOVE_THR

# isolation: distance to nearest other cow in the same frame, in box heights
def nn_dist(g):
    if len(g) < 2: return pd.Series(np.nan, index=g.index)
    p = g[["foot_u", "foot_v"]].to_numpy(); h = g.h.to_numpy()
    D = np.linalg.norm(p[:, None] - p[None], axis=2) / np.maximum(h[:, None], 1); np.fill_diagonal(D, np.inf)
    return pd.Series(D.min(1), index=g.index)
d["nn"] = d.groupby("ts", group_keys=False).apply(nn_dist)

# cows identified at the bunk by the front cameras
front = []
for cam in ("cam01", "cam02"):
    try:
        f = pd.read_parquet(f"out/ids_{cam}.parquet"); f = f[f.cow_id != "UNK"][["cow_id", "ts"]]; f["cam"] = cam; front.append(f)
    except Exception:
        pass
front = pd.concat(front) if front else pd.DataFrame(columns=["cow_id", "ts", "cam"])
front["ts"] = pd.to_datetime(front.ts)
front["minute"] = front.ts.dt.floor("min")
front = front[front.ts.dt.normalize().isin(DAYS)]
front_min = front.groupby(["cow_id", "minute"]).agg(front_bunk_obs=("ts", "size"), front_cam=("cam", lambda s: s.mode().iat[0])).reset_index()

d["minute"] = d.ts.dt.floor("min")
m = d.groupby(["cow_id", "minute"]).agg(
    n_obs=("ts", "size"), frac_bunk=("bunk3", "mean"), frac_water=("water", "mean"),
    frac_lying=("lying", "mean"), frac_moving=("moving", "mean"), move_sum=("move", "sum"),
    nn_median=("nn", "median"), id_conf=("id_conf", "mean"),
    frac_continuous=("id_source", lambda s: (s == "observed_continuous").mean())).reset_index()

# full grid: every cow x every minute of both days
days = DAYS
cows = sorted(d.cow_id.unique())
grid = pd.MultiIndex.from_product([cows, pd.date_range(days[0], days[-1] + pd.Timedelta(hours=23, minutes=59), freq="min")],
                                  names=["cow_id", "minute"]).to_frame(index=False)
m = grid.merge(m, how="left").merge(front_min, how="left")
m["n_obs"] = m.n_obs.fillna(0).astype(int); m["front_bunk_obs"] = m.front_bunk_obs.fillna(0).astype(int)
m["at_bunk"] = (m.frac_bunk.fillna(0) >= 0.4) | (m.front_bunk_obs >= 5)
m["day"] = np.where(m.minute.dt.normalize() == days[0], "Day 1", "Day 2")


def label(r):
    if r.n_obs == 0 and r.front_bunk_obs == 0: return "other_not_visible", 0.0, "none"
    if r.at_bunk and (r.frac_lying if pd.notna(r.frac_lying) else 0) < 0.5:
        conf = max(r.frac_bunk if pd.notna(r.frac_bunk) else 0, min(1, r.front_bunk_obs / 15))
        return "feeding", conf, (r.front_cam if r.front_bunk_obs >= 5 else "cam03")
    if (r.frac_water if pd.notna(r.frac_water) else 0) >= 0.3: return "drinking", r.frac_water, "cam03"
    if (r.frac_moving if pd.notna(r.frac_moving) else 0) >= 0.4: return "walking", r.frac_moving, "cam03"
    if r.frac_lying >= 0.5: return "lying", r.frac_lying, "cam03"
    return "standing", 1 - r.frac_lying, "cam03"


lab = m.apply(label, axis=1, result_type="expand"); lab.columns = ["behavior", "confidence", "camera"]
m = pd.concat([m, lab], axis=1)
m["confidence"] = m.confidence.astype(float).round(2)
m["evidence"] = np.where((m.n_obs >= 10) & (m.frac_continuous.fillna(0) >= 0.8) & (m.confidence >= 0.6), "observed", "estimated")
m.loc[m.behavior == "other_not_visible", "evidence"] = "estimated"
m["method"] = "rule"

m.to_parquet("out/minute_features.parquet", index=False)
cols = ["cow_id", "day", "minute", "behavior", "camera", "confidence", "evidence", "method", "n_obs"]
m[cols].to_csv("out/activity_minutes.csv", index=False)

# bouts
m = m.sort_values(["cow_id", "minute"])
new = (m.behavior != m.behavior.shift()) | (m.cow_id != m.cow_id.shift()) | (m.day != m.day.shift())
m["bout"] = new.cumsum()
act = m.groupby("bout").agg(cow_id=("cow_id", "first"), day=("day", "first"), start_time=("minute", "first"),
                            end_time=("minute", "last"), behavior=("behavior", "first"),
                            camera=("camera", lambda s: s.mode().iat[0]), confidence=("confidence", "mean"),
                            evidence=("evidence", lambda s: "observed" if (s == "observed").mean() >= 0.5 else "estimated"),
                            method=("method", "first")).reset_index(drop=True)
act["end_time"] = act.end_time + pd.Timedelta(minutes=1)
act["confidence"] = act.confidence.round(2)
act.to_csv("out/activity.csv", index=False)

tb = m.pivot_table(index=["cow_id", "day"], columns="behavior", values="minute", aggfunc="count", fill_value=0)
tb.to_csv("out/time_budget.csv")
print("activity.csv bouts:", len(act), "| cow-minutes:", len(m))
print(tb.to_string())
print("\nevidence share:", m.evidence.value_counts(normalize=True).round(3).to_dict())
