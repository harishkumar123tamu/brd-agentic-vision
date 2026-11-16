"""Pen 6 BRD watch: dashboard for Level 1 + Level 2 outputs.

Run from the repository root:
    pip install streamlit plotly pandas
    streamlit run dashboard/brd_dashboard.py

Reads only files in this repo:
  outputs/brd_risk.csv, outputs/brd_features.csv, outputs/time_budget.csv, outputs/activity_minutes.csv,
  outputs/id_check/<cam>/*.jpg, outputs/traces/selected/*/trace.md (+ images), docs/clips/*.mp4 + index.csv
"""
from pathlib import Path
import re
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
OUT, CLIPS = ROOT / "outputs", ROOT / "docs" / "clips"
BEHAVIOR_ORDER = ["feeding", "drinking", "walking", "standing", "lying", "ruminating_standing", "ruminating_lying",
                  "grooming", "social_interaction", "other_not_visible"]
COLORS = {"feeding": "#2E7D32", "drinking": "#1E88E5", "walking": "#F9A825", "standing": "#8D6E63", "lying": "#6A1B9A",
          "ruminating_standing": "#00897B", "ruminating_lying": "#AD1457", "grooming": "#5E35B1",
          "social_interaction": "#EF6C00", "other_not_visible": "#BDBDBD"}

st.set_page_config(page_title="Pen 6 BRD watch", layout="wide")


@st.cache_data
def load():
    risk = pd.read_csv(OUT / "brd_risk.csv").sort_values("rank")
    feats = pd.read_csv(OUT / "brd_features.csv") if (OUT / "brd_features.csv").exists() else pd.DataFrame()
    tb = pd.read_csv(OUT / "time_budget.csv")
    am = pd.read_csv(OUT / "activity_minutes.csv", parse_dates=["minute"]) if (OUT / "activity_minutes.csv").exists() else pd.DataFrame()
    clips = pd.read_csv(CLIPS / "index.csv") if (CLIPS / "index.csv").exists() else pd.DataFrame()
    return risk, feats, tb, am, clips


risk, feats, tb, am, clips = load()
tb_long = tb.melt(id_vars=["cow_id", "day"], var_name="behavior", value_name="minutes")

# ---------------------------------------------------------------- header
st.title("Pen 6: BRD early-warning dashboard")
st.caption("10 Angus cows · 3 cameras · 2 days (Nov 7–8). Risk = behavior compared with the herd and with the cow's own "
           "previous day. **It ranks cows for a closer look; it is not a diagnosis** (no clinical records were available).")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Cows tracked", risk.cow_id.nunique())
c2.metric("Cow-minutes labeled", f"{len(am):,}" if len(am) else "n/a")
if len(am):
    c3.metric("Observed (clear view)", f"{(am.evidence == 'observed').mean():.0%}")
    c4.metric("Not visible", f"{(am.behavior == 'other_not_visible').mean():.0%}")

tab_rank, tab_cow, tab_herd, tab_ids, tab_agent = st.tabs(
    ["Risk ranking", "Cow detail", "Herd rhythm", "ID-check frames", "Agent traces"])

# ---------------------------------------------------------------- ranking
with tab_rank:
    fig = px.bar(risk, x="cow_id", y="risk_score", color="risk_score", range_y=[0, 1],
                 color_continuous_scale=["#4CAF50", "#FFC107", "#E53935"], text="rank",
                 labels={"risk_score": "BRD risk score (0–1)", "cow_id": "Cow"})
    fig.update_traces(texttemplate="#%{text}", textposition="outside")
    fig.update_layout(coloraxis_showscale=False, height=380)
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(risk[["rank", "cow_id", "risk_score", "top_reasons"]], hide_index=True, use_container_width=True)
    st.info("Top reasons are written as: this cow vs the herd median on Day 2, and Day 2 vs her own Day 1. "
            "Feeding, lying and walking are per **visible** hour, so cows that were often hidden are not penalised.")

# ---------------------------------------------------------------- cow detail
with tab_cow:
    cow = st.selectbox("Cow", list(risk.cow_id), index=0)
    r = risk.set_index("cow_id").loc[cow]
    a, b = st.columns([1, 2])
    a.metric(f"{cow} risk score", f"{r.risk_score:.2f}", f"rank {int(r['rank'])} of {len(risk)}")
    b.markdown(f"**Why:** {r.top_reasons}")

    d = tb_long[tb_long.cow_id == cow]
    herd = tb_long.groupby(["day", "behavior"]).minutes.median().reset_index().assign(cow_id="herd median")
    comp = pd.concat([d, herd])
    fig = px.bar(comp, x="minutes", y="cow_id", color="behavior", orientation="h", facet_row="day",
                 category_orders={"behavior": BEHAVIOR_ORDER}, color_discrete_map=COLORS,
                 title=f"Time budget: {cow} vs herd median (minutes per day)")
    fig.update_layout(height=420)
    st.plotly_chart(fig, use_container_width=True)

    if len(feats):
        f = feats[feats.cow_id == cow]
        cols = [c for c in ["day", "feed_min_per_vis_h", "bunk_visits", "lying_min_per_vis_h", "walk_min_per_vis_h",
                            "isolation", "visible_min"] if c in f.columns]
        st.markdown("**Features** (per visible hour; isolation = distance to nearest cow in body-heights)")
        st.dataframe(f[cols].round(2), hide_index=True, use_container_width=True)

    if len(am):
        x = am[am.cow_id == cow].copy()
        x["hour"] = x.minute.dt.floor("h")
        hourly = x.assign(feeding=x.behavior.eq("feeding"), lying=x.behavior.isin(["lying", "ruminating_lying"])) \
                  .groupby("hour")[["feeding", "lying"]].sum().reset_index()
        hh = am.assign(hour=am.minute.dt.floor("h"), feeding=am.behavior.eq("feeding")) \
               .groupby(["hour", "cow_id"]).feeding.sum().groupby("hour").median().reset_index(name="herd_feeding")
        hourly = hourly.merge(hh, on="hour", how="left")
        fig = px.line(hourly, x="hour", y=["feeding", "herd_feeding", "lying"],
                      labels={"value": "minutes in the hour", "hour": ""},
                      title=f"{cow}: feeding and lying per hour across both days (herd median feeding for comparison)")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Evidence clips** (15 s, cow in the red box)")
    if len(clips):
        cc = clips[clips.cow_id == cow]
        if cc.empty: st.write("No clips for this cow (clips are made for the top-3 cows).")
        for row in cc.itertuples():
            p = CLIPS / Path(str(row.clip)).name
            if p.exists():
                st.markdown(f"*{row.kind.replace('_', ' ')}* · {row.camera} · {row.time} · {row.description}")
                st.video(str(p))

# ---------------------------------------------------------------- herd rhythm
with tab_herd:
    if len(am):
        day = st.radio("Day", sorted(am.day.unique()), horizontal=True)
        y = am[am.day == day].copy(); y["hour"] = y.minute.dt.hour
        share = y.groupby(["hour", "behavior"]).size().reset_index(name="n")
        share["share"] = share.n / share.groupby("hour").n.transform("sum")
        fig = px.area(share, x="hour", y="share", color="behavior", category_orders={"behavior": BEHAVIOR_ORDER},
                      color_discrete_map=COLORS, title=f"Herd daily rhythm, {day} (share of cow-minutes per hour)")
        st.plotly_chart(fig, use_container_width=True)
        heat = y.assign(feeding=y.behavior.eq("feeding")).groupby(["cow_id", "hour"]).feeding.sum().reset_index()
        fig = px.density_heatmap(heat, x="hour", y="cow_id", z="feeding", histfunc="sum", nbinsx=24,
                                 color_continuous_scale="Greens", title=f"Feeding minutes per cow per hour, {day}")
        st.plotly_chart(fig, use_container_width=True)
    st.markdown("**Overall time budgets**")
    st.dataframe(tb, hide_index=True, use_container_width=True)

# ---------------------------------------------------------------- ID check
with tab_ids:
    st.caption("Every 30 minutes on each camera: boxes with cow IDs (C01–C10) and ID confidence. "
               "Cam 01/02 show IDs only for cows at the feed bunk.")
    cams = sorted(p.name for p in (OUT / "id_check").glob("cam*") if p.is_dir())
    if cams:
        cam = st.radio("Camera", cams, horizontal=True)
        files = sorted((OUT / "id_check" / cam).glob("*.jpg"))
        if files:
            pick = st.select_slider("Time slot", options=[f.stem for f in files])
            st.image(str(OUT / "id_check" / cam / f"{pick}.jpg"), use_container_width=True)

# ---------------------------------------------------------------- agent traces
with tab_agent:
    st.caption("The vision-language agent plans which tools to use (view, zoom, look ±20 s, other camera, zone check), "
               "answers, checks itself against geometry and the rule label, and re-answers. v1 failed (overrode a correct "
               "'feeding' label from a cow seen from behind); v2 added guard-rails and keeps the rule label when a conflict "
               "is unresolved.")
    tdirs = sorted((OUT / "traces" / "selected").glob("*/"))
    if tdirs:
        t = st.selectbox("Trace", [p.name for p in tdirs])
        tdir = OUT / "traces" / "selected" / t
        md = (tdir / "trace.md").read_text() if (tdir / "trace.md").exists() else ""
        # render text with images inline
        for chunk in re.split(r"(!\[\]\([^)]+\))", md):
            m = re.match(r"!\[\]\(([^)]+)\)", chunk)
            if m:
                img = tdir / m.group(1)
                if img.exists(): st.image(str(img), width=260)
            elif chunk.strip():
                st.markdown(chunk)
