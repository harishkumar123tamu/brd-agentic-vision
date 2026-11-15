
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Pen 6 BRD Monitoring",
    layout="wide"
)

st.title("Pen 6 - BRD Risk Monitoring")

source = Path("level2/risk_source.txt")
if source.exists():
    st.warning(source.read_text())
else:
    st.warning("Data source not verified")

risk = pd.read_csv("level2/brd_risk.csv")
features = pd.read_csv("level2/features.csv")

st.subheader("BRD Risk Ranking")
st.bar_chart(
    risk.set_index("cow_id")["risk_score"]
)

st.dataframe(
    risk,
    width="stretch",
    hide_index=True
)

st.subheader("Individual Cow Analysis")

cow = st.selectbox(
    "Select Cow",
    risk["cow_id"].tolist()
)

selected = risk[risk.cow_id == cow].iloc[0]

col1, col2 = st.columns(2)
col1.metric("Risk Score", f"{selected.risk_score:.3f}")
col2.metric("Herd Risk Rank", int(selected["rank"]))

st.write("**Risk indicators:**", selected.top_reasons)

cow_features = features[
    features.cow_id == cow
].sort_values("day")

st.subheader("Daily Behavior Features")
st.dataframe(cow_features, width="stretch")

st.caption(
    "Experimental risk ranking only. "
    "Not a veterinary diagnosis."
)
