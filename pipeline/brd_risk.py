"""Step 14 (Level 2): BRD risk score per cow from behavior features -> brd_risk.csv

Usage:  python code/brd_risk.py
Reads:  out/minute_features.parquet (from activity.py)
Writes: out/brd_risk.csv        cow_id, risk_score (0-1), rank, top_reasons
        out/brd_features.csv    per cow per day features + herd z-scores (for the dashboard / brief)

Biology: cattle developing BRD tend to eat less (shorter bunk time, fewer bunk visits), lie more,
move less and stand apart from the herd, often before clinical signs. A CHANGE matters most:
a cow doing less than the herd, or less than she did the day before.
Score = weighted sum of herd z-scores (sign set so positive = more worrying) on Day 2 plus the
Day 1 -> Day 2 change, squashed to 0-1. Weights fixed in advance (not tuned to an outcome).
This ranks cows for a closer look; it is NOT a diagnosis (no clinical ground truth).
"""
import numpy as np, pandas as pd

m = pd.read_parquet("out/minute_features.parquet")
m["feeding"] = m.behavior.eq("feeding"); m["lying_b"] = m.behavior.eq("lying"); m["walking"] = m.behavior.eq("walking")
m["visible"] = m.n_obs > 0
m = m.sort_values(["cow_id", "minute"])
m["visit_start"] = m.feeding & ~m.groupby("cow_id").feeding.shift(fill_value=False)

f = m.groupby(["cow_id", "day"]).agg(
    feed_min=("feeding", "sum"), bunk_visits=("visit_start", "sum"), lying_min=("lying_b", "sum"),
    walk_min=("walking", "sum"), isolation=("nn_median", "median"), visible_min=("visible", "sum")).reset_index()
# normalise by visible minutes so a cow that is often hidden is not penalised for "not feeding"
for c in ["feed_min", "lying_min", "walk_min"]:
    f[c + "_per_vis_h"] = (f[c] / f.visible_min.clip(lower=1) * 60).round(2)

SIGN = {"feed_min_per_vis_h": -1, "bunk_visits": -1, "lying_min_per_vis_h": +1, "walk_min_per_vis_h": -1, "isolation": +1}
W = {"feed_min_per_vis_h": 0.30, "bunk_visits": 0.15, "lying_min_per_vis_h": 0.20, "walk_min_per_vis_h": 0.10, "isolation": 0.10}
W_CHANGE = 0.15
NAME = {"feed_min_per_vis_h": "feeding time", "bunk_visits": "bunk visits", "lying_min_per_vis_h": "lying time",
        "walk_min_per_vis_h": "walking/activity", "isolation": "distance from other cows"}

for c in SIGN:
    g = f.groupby("day")[c]
    f[c + "_z"] = (SIGN[c] * (f[c] - g.transform("median")) / g.transform("std").replace(0, np.nan)).fillna(0).clip(-3, 3)
f.to_csv("out/brd_features.csv", index=False)

d1, d2 = f[f.day == "Day 1"].set_index("cow_id"), f[f.day == "Day 2"].set_index("cow_id")
rows = []
for cow in d2.index:
    contrib = {c: W[c] * d2.at[cow, c + "_z"] for c in SIGN}
    # change vs own Day 1 (feeding drop + lying rise), in herd-z units
    if cow in d1.index:
        ch = (-(d2.at[cow, "feed_min_per_vis_h"] - d1.at[cow, "feed_min_per_vis_h"]) / (f.feed_min_per_vis_h.std() or 1)
              + (d2.at[cow, "lying_min_per_vis_h"] - d1.at[cow, "lying_min_per_vis_h"]) / (f.lying_min_per_vis_h.std() or 1)) / 2
        contrib["change_vs_day1"] = W_CHANGE * float(np.clip(ch, -3, 3))
    raw = sum(contrib.values())
    reasons = []
    for k, v in sorted(contrib.items(), key=lambda kv: -kv[1])[:3]:
        if v <= 0.02: continue
        if k == "change_vs_day1":
            reasons.append(f"feeding {d2.at[cow,'feed_min_per_vis_h']:.0f} vs {d1.at[cow,'feed_min_per_vis_h']:.0f} min/visible-h and "
                           f"lying {d2.at[cow,'lying_min_per_vis_h']:.0f} vs {d1.at[cow,'lying_min_per_vis_h']:.0f} (Day 2 vs Day 1)")
        else:
            med = f[f.day == "Day 2"][k].median()
            direction = "below" if SIGN[k] < 0 else "above"
            reasons.append(f"{NAME[k]} {d2.at[cow,k]:.1f} vs herd median {med:.1f} ({direction} herd)")
    rows.append(dict(cow_id=cow, raw=raw, top_reasons="; ".join(reasons) if reasons else "no behavior notably outside the herd range"))
r = pd.DataFrame(rows)
r["risk_score"] = (1 / (1 + np.exp(-3 * r.raw))).round(3)
r = r.sort_values("risk_score", ascending=False)
r["rank"] = range(1, len(r) + 1)
r[["cow_id", "risk_score", "rank", "top_reasons"]].to_csv("out/brd_risk.csv", index=False)
print(r[["rank", "cow_id", "risk_score", "top_reasons"]].to_string(index=False))
