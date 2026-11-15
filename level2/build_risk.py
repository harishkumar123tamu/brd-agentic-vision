
from pathlib import Path
import numpy as np
import pandas as pd

Path("data_local").mkdir(exist_ok=True)
Path("level2").mkdir(exist_ok=True)

real_file = Path("data_local/activity.csv")

if real_file.exists():
    df = pd.read_csv(real_file)
    source = "REAL ACTIVITY - verify coverage and accuracy"
else:
    source = "SIMULATED DEMO - NOT REAL BRD RESULTS"
    rng = np.random.default_rng(42)
    behaviors = [
        "lying", "standing", "walking", "feeding",
        "drinking", "ruminating_lying",
        "ruminating_standing", "grooming",
        "social_interaction", "other_not_visible"
    ]
    probs = np.array([
        .35, .15, .05, .15, .02,
        .15, .05, .02, .02, .04
    ])
    rows = []
    for day in (1, 2):
        for n in range(1, 11):
            p = probs.copy()
            if day == 2 and n == 7:
                p[3] *= 0.5
                p[0] *= 1.4
            p /= p.sum()
            for minute, b in enumerate(
                rng.choice(behaviors, 1440, p=p)
            ):
                rows.append([f"C{n:02d}", day, minute, b])

    df = pd.DataFrame(
        rows,
        columns=["cow_id", "day", "start_time", "behavior"]
    )
    df.to_csv("data_local/activity_fake.csv", index=False)

required = {"cow_id", "day", "start_time", "behavior"}
if not required.issubset(df.columns):
    raise ValueError("activity.csv is missing required columns")

df = df.sort_values(["cow_id", "day", "start_time"])
records = []

for (cow, day), group in df.groupby(["cow_id", "day"]):
    b = group["behavior"]
    records.append({
        "cow_id": cow,
        "day": day,
        "feed_min": (b == "feeding").sum(),
        "feed_visits": (
            (b == "feeding") & (b.shift() != "feeding")
        ).sum(),
        "drink_visits": (
            (b == "drinking") & (b.shift() != "drinking")
        ).sum(),
        "lying_min": b.isin([
            "lying", "ruminating_lying"
        ]).sum(),
        "rumination_min": b.isin([
            "ruminating_lying", "ruminating_standing"
        ]).sum(),
        "active_min": b.isin([
            "walking", "grooming", "social_interaction"
        ]).sum(),
        "not_visible_min": (
            b == "other_not_visible"
        ).sum()
    })

features = pd.DataFrame(records)
features.to_csv("level2/features.csv", index=False)

def zscore(values, direction=1):
    values = values.astype(float)
    std = values.std(ddof=0)
    if std == 0:
        return values * 0
    return direction * (values - values.mean()) / std

last = features[features.day == features.day.max()]
last = last.set_index("cow_id")

feed = zscore(last.feed_min, -1)
visits = (
    zscore(last.feed_visits, -1) +
    zscore(last.drink_visits, -1)
) / 2
lying = zscore(last.lying_min, 1)
rumination = zscore(last.rumination_min, -1)

change = pd.Series(0.0, index=last.index)
if features.day.nunique() > 1:
    prev_day = sorted(features.day.unique())[-2]
    prev = features[features.day == prev_day]
    prev = prev.set_index("cow_id")
    common = last.index.intersection(prev.index)
    for feature, direction in [
        ("feed_min", -1),
        ("lying_min", 1),
        ("rumination_min", -1)
    ]:
        diff = last.loc[common, feature] - prev.loc[common, feature]
        change.loc[common] += zscore(diff, direction) / 3

# Isolation is omitted until tracks.parquet is available.
contributions = pd.DataFrame({
    "Feeding below herd average": .30 * feed,
    "Fewer feeding/drinking visits": .15 * visits,
    "More lying time": .20 * lying,
    "Less rumination": .15 * rumination,
    "Day-to-day behavior change": .10 * change
})

raw = contributions.sum(axis=1)
risk = pd.DataFrame({
    "cow_id": last.index,
    "risk_score": 1 / (1 + np.exp(-raw))
})
risk = risk.sort_values(
    "risk_score", ascending=False
).reset_index(drop=True)
risk["rank"] = range(1, len(risk) + 1)

def reasons(cow):
    positive = contributions.loc[cow]
    positive = positive[positive > 0].sort_values(ascending=False)
    if positive.empty:
        return "No clearly elevated indicators in available features"
    return "; ".join(positive.head(3).index)

risk["top_reasons"] = risk.cow_id.map(reasons)
risk.to_csv("level2/brd_risk.csv", index=False)

Path("level2/risk_source.txt").write_text(
    source + "\nIsolation unavailable; ranking is not a diagnosis."
)

print("SUCCESS! BRD risk scoring completed.")
print("Source:", source)
print("Created level2/features.csv")
print("Created level2/brd_risk.csv")
print(risk.to_string(index=False))

