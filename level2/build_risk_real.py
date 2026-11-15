"""Calculate transparent BRD WATCH scores from cow activity (not diagnoses).

Run, for demo:
  python level2/build_risk_real.py --activity data_local/activity_fake.csv
Run with real data once Suhas sends it:
  python level2/build_risk_real.py --activity data_local/activity.csv --tracks data_local/tracks.parquet

The 0..1 score is a RELATIVE HEURISTIC, not a calibrated disease probability.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd

ACTIVITY_COLUMNS = ["cow_id", "day", "start_time", "end_time", "behavior", "camera",
                    "confidence", "evidence", "method"]
BEHAVIORS = {"lying", "standing", "walking", "feeding", "drinking", "ruminating_lying",
             "ruminating_standing", "grooming", "social_interaction", "other_not_visible"}
# Agreed weights from the task guide; omitted features have their weights redistributed.
WEIGHTS = {"feed_min": .30, "feed_visits": .15, "lying_min": .20,
           "rumination_min": .15, "isolation_map_units": .10, "change": .10}
SIGN = {"feed_min": -1, "feed_visits": -1, "lying_min": 1,
        "rumination_min": -1, "isolation_map_units": 1}


def load_activity(path: Path) -> pd.DataFrame:
    a = pd.read_csv(path)
    missing = sorted(set(ACTIVITY_COLUMNS) - set(a.columns))
    if missing:
        raise ValueError(f"Missing required activity.csv columns: {missing}")
    a["cow_id"] = a.cow_id.astype(str).str.strip()
    # Accept numeric days as well as text labels such as Day 1 and Day 2.
    raw_day = a.day.astype(str).str.strip()
    day_num = pd.to_numeric(raw_day, errors="coerce")
    if day_num.isna().any():
        extracted = raw_day.str.extract(r"(?i)^day[ _-]*([12])$")[0]
        day_num = day_num.fillna(pd.to_numeric(extracted, errors="coerce"))
    a["day"] = day_num
    for col in ("start_time", "end_time"):
        a[col] = pd.to_datetime(a[col], errors="coerce")
    a = a.dropna(subset=["day", "start_time", "end_time"])
    a = a[a.cow_id.str.fullmatch(r"C(0[1-9]|10)")].copy()
    invalid = set(a.behavior.dropna().unique()) - BEHAVIORS
    if invalid:
        raise ValueError(f"Unknown behavior labels: {sorted(invalid)}")
    if a.empty:
        raise ValueError("No valid activity rows were found")
    # Prioritize directly observed, agent verified, high-confidence row if cameras overlap.
    a["source_priority"] = a.evidence.astype(str).str.lower().eq("observed").astype(int)
    a["agent_priority"] = a.method.astype(str).str.lower().eq("agent_verified").astype(int)
    a["confidence_priority"] = pd.to_numeric(a.confidence, errors="coerce").fillna(0)
    a = a.sort_values(["cow_id", "day", "start_time", "source_priority", "agent_priority",
                       "confidence_priority"], ascending=[True, True, True, False, False, False])
    a = a.drop_duplicates(["cow_id", "day", "start_time"], keep="first")
    a["duration_min"] = ((a.end_time - a.start_time).dt.total_seconds() / 60).clip(0, 60)
    a = a[a.duration_min > 0].sort_values(["cow_id", "day", "start_time"]).copy()
    return a


def compute_features(a: pd.DataFrame) -> pd.DataFrame:
    all_features = []
    for (cow, day), group in a.groupby(["cow_id", "day"], sort=True):
        g = group.sort_values("start_time").copy()
        prev_behavior = g.behavior.shift(1)
        gap_minutes = (g.start_time - g.end_time.shift(1)).dt.total_seconds() / 60
        interrupted = gap_minutes.isna() | (gap_minutes > .1)
        first_feed = g.behavior.eq("feeding") & (prev_behavior.ne("feeding") | interrupted)
        first_drink = g.behavior.eq("drinking") & (prev_behavior.ne("drinking") | interrupted)
        lying = g.behavior.isin(["lying", "ruminating_lying"])
        first_lying = lying & (~lying.shift(1, fill_value=False) | interrupted)

        def minutes_of(*classes):
            return round(g.loc[g.behavior.isin(classes), "duration_min"].sum(), 2)

        all_features.append({
            "cow_id": cow, "day": int(day),
            "coverage_min": round(g.duration_min.sum(), 2),
            "observed_min": round(g.loc[g.evidence.astype(str).str.lower().eq("observed"),
                                        "duration_min"].sum(), 2),
            "feed_min": minutes_of("feeding"), "feed_visits": int(first_feed.sum()),
            "drink_visits": int(first_drink.sum()),
            "lying_min": minutes_of("lying", "ruminating_lying"),
            "lying_bouts": int(first_lying.sum()),
            "rumination_min": minutes_of("ruminating_lying", "ruminating_standing"),
            "active_min": minutes_of("walking", "social_interaction", "grooming"),
            "not_visible_min": minutes_of("other_not_visible"),
        })
    return pd.DataFrame(all_features)


def add_isolation(f: pd.DataFrame, path: Path | None) -> pd.DataFrame:
    f["isolation_map_units"] = np.nan
    if path is None:
        print("No tracks.parquet supplied: isolation omitted from score.")
        return f
    t = pd.read_parquet(path)
    required = {"cow_id", "day", "ts", "pen_x", "pen_y"}
    if not required.issubset(t.columns):
        raise ValueError(f"tracks.parquet lacks: {sorted(required - set(t.columns))}")
    t = t[list(required)].copy()
    raw_day = t.day.astype(str).str.strip()
    day_num = pd.to_numeric(raw_day, errors="coerce")
    if day_num.isna().any():
        day_num = day_num.fillna(pd.to_numeric(raw_day.str.extract(r"(?i)^day[ _-]*([12])$")[0], errors="coerce"))
    t["day"] = day_num
    t["ts"] = pd.to_datetime(t.ts, errors="coerce")
    for col in ("pen_x", "pen_y"):
        t[col] = pd.to_numeric(t[col], errors="coerce")
    t = t.dropna(subset=["ts", "day", "pen_x", "pen_y"])
    t = t[t.cow_id.astype(str).str.fullmatch(r"C(0[1-9]|10)")].copy()
    if t.empty:
        print("No mapped cow positions available; isolation omitted.")
        return f
    # Fuse same-cow observations across cameras at a given one-minute window.
    t["minute"] = t.ts.dt.floor("min")
    per_cow = t.groupby(["day", "minute", "cow_id"], as_index=False)[["pen_x", "pen_y"]].median()
    centre = per_cow.groupby(["day", "minute"])[["pen_x", "pen_y"]].median().rename(
        columns={"pen_x": "herd_x", "pen_y": "herd_y"}).reset_index()
    per_cow = per_cow.merge(centre, on=["day", "minute"])
    per_cow["distance"] = np.hypot(per_cow.pen_x - per_cow.herd_x,
                                   per_cow.pen_y - per_cow.herd_y)
    dist = per_cow.groupby(["cow_id", "day"], as_index=False).distance.mean()
    dist = dist.rename(columns={"distance": "from_tracks"})
    merged = f.merge(dist, on=["cow_id", "day"], how="left")
    merged["isolation_map_units"] = merged["from_tracks"]
    return merged.drop(columns=["from_tracks"])


def robust_z(value, mean, std, direction=1):
    if not np.isfinite(value) or not np.isfinite(mean) or not np.isfinite(std) or std < 1e-8:
        return 0.0
    return float(np.clip(direction * (value - mean) / std, -4, 4))


def format_reason(feature, val, herd_mean):
    if feature == "feed_min":
        diff = (1 - val / herd_mean) * 100 if herd_mean > 0 else 0
        return f"Feeding time {diff:.0f}% below day-2 herd average" if diff > 0 else "Lower feeding time than peers"
    if feature == "feed_visits":
        return f"Fewer feeding visits ({val:.0f} vs herd avg {herd_mean:.1f})"
    if feature == "lying_min":
        return f"More lying ({val:.0f} min vs herd avg {herd_mean:.0f} min)"
    if feature == "rumination_min":
        return f"Less rumination ({val:.0f} min vs herd avg {herd_mean:.0f} min)"
    if feature == "isolation_map_units":
        return "Farther from herd center (pen-map units; not meters)"
    if feature == "change":
        return "Worrying activity change compared with own day 1"
    return feature


def score(f: pd.DataFrame) -> pd.DataFrame:
    days = sorted(f.day.unique())
    if not days:
        raise ValueError("No feature rows")
    final_day = days[-1]
    current = f[f.day.eq(final_day)].copy()
    past = f[f.day.eq(days[-2])].set_index("cow_id") if len(days) > 1 else None
    day1 = f[f.day.eq(days[-2])] if len(days) > 1 else None
    out = []
    for _, row in current.iterrows():
        contributions = {}
        for field, direction in SIGN.items():
            if pd.isna(row[field]):
                continue
            herd = current[field].dropna()
            contributions[field] = robust_z(row[field], herd.mean(), herd.std(ddof=0), direction)
        if past is not None and row.cow_id in past.index:
            prev = past.loc[row.cow_id]
            changes = []
            for field, direction in SIGN.items():
                if pd.isna(row[field]) or pd.isna(prev[field]):
                    continue
                baseline_std = day1[field].std(ddof=0)
                if pd.notna(baseline_std) and baseline_std >= 1e-8:
                    changes.append(robust_z(row[field] - prev[field], 0, baseline_std, direction))
            if changes:
                contributions["change"] = float(np.mean(changes))
        effective_weight = sum(WEIGHTS[k] for k in contributions)
        raw = sum(WEIGHTS[k] * z for k, z in contributions.items()) / effective_weight if effective_weight else 0
        risk = float(1 / (1 + np.exp(-raw)))
        means = {field: current[field].dropna().mean() if not current[field].dropna().empty else np.nan for field in SIGN}
        positives = sorted(((WEIGHTS[k] * z, k) for k, z in contributions.items() if z > .1), reverse=True)
        reasons = [format_reason(field, row.get(field, np.nan), means.get(field, np.nan))
                   for _, field in positives[:3]]
        if not reasons:
            reasons = ["No clear worrying deviation; confirm data quality and review video"]
        out.append({"cow_id": row.cow_id, "risk_score": round(risk, 4),
                    "top_reasons": "; ".join(reasons)})
    result = pd.DataFrame(out).sort_values(["risk_score", "cow_id"], ascending=[False, True])
    result["rank"] = range(1, len(result) + 1)
    return result[["cow_id", "risk_score", "rank", "top_reasons"]]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--activity", type=Path, required=True)
    ap.add_argument("--source", choices=["demo", "real", "unverified"], default="unverified",
                    help="Mark input provenance. Use 'real' only after confirming actual cow activity data; default is unverified.")
    ap.add_argument("--tracks", type=Path, default=None)
    ap.add_argument("--risk-out", type=Path, default=Path("level2/brd_risk.csv"))
    ap.add_argument("--features-out", type=Path, default=Path("level2/features.csv"))
    args = ap.parse_args()
    name_demo = any(token in args.activity.name.lower() for token in ("fake", "demo", "simulat"))
    if args.source == "real" and name_demo:
        raise SystemExit("Refusing --source real for a file named fake/demo/simulated.")
    source_status = "demo" if (name_demo or args.source == "demo") else args.source
    print("INPUT STATUS:", source_status.upper())
    if source_status != "real":
        print("WARNING: these outputs must not be submitted as actual cattle BRD findings.")
    a = load_activity(args.activity)
    f = add_isolation(compute_features(a), args.tracks)
    insufficient = f[f.coverage_min < 1200]
    if not insufficient.empty:
        print("WARNING: Less than 1,200 min coverage for some cow-days; low coverage can distort risk.")
        print(insufficient[["cow_id", "day", "coverage_min"]].to_string(index=False))
    if f.cow_id.nunique() < 10:
        print("WARNING: Fewer than 10 distinct cows present in input.")
    r = score(f)
    for output in (args.risk_out, args.features_out):
        output.parent.mkdir(parents=True, exist_ok=True)
    r.to_csv(args.risk_out, index=False)
    f.to_csv(args.features_out, index=False)
    metadata_path = args.risk_out.parent / "risk_source.json"
    metadata_path.write_text(json.dumps({
        "activity_file": str(args.activity).replace("\\", "/"),
        "tracks_file": str(args.tracks).replace("\\", "/") if args.tracks else None,
        "is_simulated": source_status == "demo",
        "source_status": source_status,
        "input_rows": int(len(a)),
        "cow_count": int(f.cow_id.nunique()),
        "days": sorted(int(v) for v in f.day.unique()),
        "minimum_cow_day_coverage_min": float(f.coverage_min.min()),
        "total_observed_min": float(f.observed_min.sum()),
        "total_coverage_min": float(f.coverage_min.sum()),
        "note": "Risk score is a relative watch-list heuristic, NOT BRD diagnosis or probability"
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.risk_out}, {args.features_out}, and {metadata_path}")
    print("Relative heuristic scores only: NOT diagnosis or calibrated disease probabilities")
    print(r.to_string(index=False, max_colwidth=70))


if __name__ == "__main__":
    main()
