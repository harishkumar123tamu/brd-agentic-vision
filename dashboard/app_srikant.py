"""Local Streamlit visualization of BRD WATCH scores.

From project root: streamlit run dashboard/app_srikant.py
"""
from pathlib import Path
import json
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Pen 6 BRD Watch", layout="wide")
st.title("Pen 6: Behavior and BRD Risk Watch")
st.caption("Decision-support prototype only. Scores rank video patterns for review; they do not diagnose BRD.")

risk_path = Path("level2/brd_risk.csv")
source_path = Path("level2/risk_source.json")
source = json.loads(source_path.read_text(encoding="utf-8")) if source_path.exists() else None
if source:
    activity_path = Path(source["activity_file"])
else:
    activity_path = Path("data_local/activity_fake.csv")
    st.warning("No risk_source.json provenance: using fake activity unless regenerated from real data.")
if not risk_path.exists():
    st.error("No risk file. Run: py -3.12 level2/build_risk_real.py --activity data_local/activity.csv")
    st.stop()
if not activity_path.exists():
    st.error(f"No activity file at {activity_path}. Run the fake-data generator or add Suhas's activity.csv")
    st.stop()
if source and source.get('source_status') == 'real':
    st.info('Input marked as real activity. Verify coverage, identity and video evidence before reporting results.')
elif source and source.get('source_status') == 'demo':
    st.warning('SIMULATED DATA: scores and rankings are demonstration outputs only.')
else:
    st.warning('UNVERIFIED INPUT: do not report this ranking as actual findings. Recalculate with --source real after verification.')

risk = pd.read_csv(risk_path).sort_values("rank")
act = pd.read_csv(activity_path)
features_path = Path("level2/features.csv")
features = pd.read_csv(features_path) if features_path.exists() else None

if risk.empty:
    st.error("Risk file is empty")
    st.stop()
left, center, right = st.columns(3)
left.metric("Cows ranked", int(risk.cow_id.nunique()))
center.metric("Highest risk-score", f"{risk.risk_score.max():.3f}")
right.metric("Top watch-list cow", risk.iloc[0].cow_id)

st.subheader("Relative risk ranking")
st.plotly_chart(px.bar(risk, x="cow_id", y="risk_score", hover_data=["rank", "top_reasons"],
                       range_y=[0, 1], labels={"cow_id": "Cow", "risk_score": "Heuristic risk score"}),
                width="stretch")
st.caption("The 0–1 score is not an estimated probability of disease. Recheck coverage and camera confidence.")

cow = st.selectbox("Inspect cow", risk.cow_id.tolist())
match = risk.set_index("cow_id").loc[cow]
st.markdown(f"**Rank:** {int(match['rank'])} | **Score:** {float(match['risk_score']):.3f}")
st.markdown(f"**Reasons:** {match['top_reasons']}")
subset = act[act.cow_id == cow].copy()
if not subset.empty:
    subset['start_time'] = pd.to_datetime(subset.start_time, errors='coerce')
    subset['end_time'] = pd.to_datetime(subset.end_time, errors='coerce')
    subset['minutes'] = ((subset.end_time - subset.start_time).dt.total_seconds() / 60).clip(lower=0, upper=60)
    times = subset.groupby(['day', 'behavior'], as_index=False)['minutes'].sum()
    times['day'] = times['day'].astype(str)
    fig = px.bar(times, x="day", y="minutes", color="behavior", barmode="stack",
                 title="Behavior time budget from timestamp durations",
                 labels={"day": "Dataset day", "minutes": "Labeled minutes"})
    st.plotly_chart(fig, width="stretch")
    if features is not None:
        herd = features.groupby('day', as_index=False)[['feed_min', 'lying_min', 'rumination_min']].median()
        herd = herd.rename(columns={'feed_min':'herd_median_feed_min','lying_min':'herd_median_lying_min',
                                    'rumination_min':'herd_median_rumination_min'})
        st.subheader('Cow compared with herd median')
        compare = features[features.cow_id.eq(cow)].merge(herd, on='day', how='left')
        st.dataframe(compare[['day', 'feed_min', 'herd_median_feed_min', 'lying_min',
                              'herd_median_lying_min', 'rumination_min', 'herd_median_rumination_min']],
                     hide_index=True, width='stretch')
        cols = [c for c in ["day", "coverage_min", "observed_min", "feed_min", "feed_visits",
                             "drink_visits", "lying_min", "rumination_min", "active_min",
                             "not_visible_min", "isolation_map_units"] if c in features.columns]
        st.subheader("Daily features & data coverage")
        st.dataframe(features.loc[features.cow_id == cow, cols], width="stretch", hide_index=True)

st.subheader("Evidence checklist")
st.write("For final judging: add 2–3 genuine clips per top-3 cow and clearly separate directly observed events from estimated ones.")
st.write('Generate evidence-card drafts only after confirming genuine activity and original clips.')
from pathlib import Path as _Path
media_dir = _Path("data_local/evidence")
videos = sorted(media_dir.glob(f"{cow}_*.mp4")) if media_dir.exists() else []
if videos:
    st.subheader("Local evidence clips (verify cow identity and times)")
    for path in videos:
        st.caption(path.name)
        st.video(str(path))
else:
    st.caption("No local evidence clips available. Supply original, verified MP4s privately in data_local/evidence/.")
