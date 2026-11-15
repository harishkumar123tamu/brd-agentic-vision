
from pathlib import Path
import shutil
import pandas as pd

activity_file = Path("outputs/activity.csv")
clip_file = Path("docs/clips/index.csv")

for file in (activity_file, clip_file):
    if not file.exists():
        raise SystemExit(f"Missing {file}. Pull the latest GitHub changes.")

a = pd.read_csv(activity_file)
c = pd.read_csv(clip_file).fillna("")

a["start"] = pd.to_datetime(a["start_time"], errors="coerce")
a["end"] = pd.to_datetime(a["end_time"], errors="coerce")
a["min"] = (a["end"] - a["start"]).dt.total_seconds() / 60

if a["min"].isna().any() or (a["min"] < 0).any():
    raise SystemExit("Invalid timestamps in activity.csv")

a["behavior"] = a["behavior"].str.strip().str.lower()

rows = []

for (cow, day), g in a.groupby(["cow_id", "day"]):
    g = g.sort_values("start")

    def minutes(labels):
        return g.loc[g.behavior.isin(labels), "min"].sum()

    feed = minutes(["feeding"])
    lie = minutes(["lying", "ruminating_lying"])
    visible = g.loc[g.behavior != "other_not_visible", "min"].sum()

    visits = 0
    prev_behavior, prev_end = None, None

    for r in g.itertuples():
        new_bout = (
            prev_behavior != "feeding"
            or prev_end is None
            or (r.start - prev_end).total_seconds() > 60
        )

        if r.behavior == "feeding" and new_bout:
            visits += 1

        prev_behavior, prev_end = r.behavior, r.end

    rows.append({
        "cow": cow,
        "day": str(day),
        "feeding": feed,
        "feed_bouts": visits,
        "lying": lie,
        "drinking": minutes(["drinking"]),
        "visible": visible,
        "feed_share": feed / visible * 100 if visible else float("nan"),
        "lying_share": lie / visible * 100 if visible else float("nan"),
    })

s = pd.DataFrame(rows)
days = sorted(s.day.unique())

metrics = [
    ("Feeding minutes", "feeding"),
    ("Estimated feeding bouts", "feed_bouts"),
    ("Lying minutes", "lying"),
    ("Drinking minutes", "drinking"),
    ("Feeding % of visible", "feed_share"),
    ("Lying % of visible", "lying_share"),
    ("Visible minutes", "visible"),
]

follow_up = {
    "C02": "Review C02 feeding and lying trends. If changes persist, request an in-person temperature and respiratory check.",
    "C08": "Check whether C08 feeding participation and lying patterns remain unusual before recommending a physical examination.",
    "C03": "Verify C03 in the unboxed 16:52 clip, then review its feeding and resting patterns.",
}

for cow in ("C02", "C08", "C03"):
    text = [
        f"# BRD risk review: {cow}",
        "",
        "**Selection:** Team-selected top-three candidate. Exact rank and risk score not verified.",
        "**Interpretation:** Relative behavior flag, not a BRD diagnosis.",
        "",
        "## Activity compared with herd medians",
        "",
        "| Measure | " + " | ".join(
            f"{d} cow / herd median" for d in days
        ) + " |",
        "|---|" + "|".join("---:" for _ in days) + "|",
    ]

    for title, key in metrics:
        cells = []

        for day in days:
            herd = s[s.day == day]
            mine = herd[herd.cow == cow]

            if mine.empty:
                cells.append("N/A")
            else:
                suffix = "%" if key.endswith("_share") else ""
                cells.append(
                    f"{mine.iloc[0][key]:.1f}{suffix} / "
                    f"{herd[key].median():.1f}{suffix}"
                )

        text.append("| " + title + " | " + " | ".join(cells) + " |")

    text += [
        "",
        "Minutes use end_time minus start_time, not CSV row counts.",
        "Feeding bouts are estimated contiguous intervals, not verified visits.",
        "Rumination and isolation are unavailable. Camera visibility varies by day.",
        "",
        "## Evidence clips",
        "",
    ]

    selected = c[c.cow_id == cow]

    for r in selected.itertuples():
        box = str(getattr(r, "box_drawn", "")).lower() == "true"

        text.append(
            f"- `{r.clip}` ({r.camera}, {r.time}): "
            f"{r.description}. "
            f"Box drawn: {'yes' if box else 'no; identity check needed'}."
        )

    if selected.empty:
        text.append("- No clips indexed for this cow.")

    text += [
        "",
        "## Observed versus estimated",
        "",
        "Clip notes come from the team index and have not been independently verified here.",
        "Activity durations and feeding bouts are model-derived estimates.",
        "One moment away from the feed bunk does not prove a full feeding was missed.",
        "",
        "## Clinical signs",
        "",
        "Ear droop, nasal discharge, head carriage, cough and breathing: **not assessed**.",
        "Original footage must be reviewed before marking signs present or absent.",
        "",
        "## Suggested action",
        "",
        follow_up[cow],
        "",
        "The full BRD score cannot be confirmed from these activity labels because rumination and isolation are missing. Do not use the old simulated risk scores.",
        "",
    ]

    output = Path("docs") / f"risk_card_{cow}.md"
    output.parent.mkdir(exist_ok=True)

    if output.exists():
        shutil.copy2(output, output.with_suffix(".md.bak"))

    output.write_text("\n".join(text), encoding="utf-8")
    print("Created", output)

print("Review clip evidence and numerical comparisons before committing.")
