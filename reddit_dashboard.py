import pandas as pd
import streamlit as st

# ============================================================
# SAFETY: Work on a copy so old features are untouched
# ============================================================
df = df.copy()

# ============================================================
# LAYER 2 — TIME AWARENESS
# ============================================================
df["Created_At"] = pd.to_datetime(df["Created_At"], errors="coerce")

df["Created_Year"] = df["Created_At"].dt.isocalendar().year
df["Created_Week"] = (
    df["Created_At"].dt.isocalendar().year.astype(str)
    + "-W"
    + df["Created_At"].dt.isocalendar().week.astype(str)
)

# ============================================================
# LAYER 3 — WEEKLY TREND ANALYSIS (OPTION B)
# ============================================================
weekly_trends = (
    df.groupby("Created_Week")
    .agg(
        Total_Posts=("Title", "count"),
        Pain_Count=("Pain_Flag", "sum"),
        Demand_Count=("Demand_Flag", "sum"),
        Cost_Count=("Cost_Flag", "sum"),
        Confusion_Count=("Confusion_Flag", "sum"),
        Avg_Insight_Priority=("Insight_Priority", "mean"),
    )
    .reset_index()
    .sort_values("Created_Week")
)

# Week-over-week % change
for col in ["Pain_Count", "Demand_Count", "Cost_Count", "Confusion_Count"]:
    weekly_trends[f"{col}_WoW_%"] = (
        weekly_trends[col].pct_change() * 100
    ).round(2)

def trend_label(x):
    if pd.isna(x):
        return "—"
    if x > 20:
        return "🔺 Rising"
    if x < -20:
        return "🔻 Declining"
    return "➖ Stable"

for col in ["Pain_Count", "Demand_Count", "Cost_Count", "Confusion_Count"]:
    weekly_trends[f"{col}_Trend"] = weekly_trends[f"{col}_WoW_%"].apply(trend_label)

# ============================================================
# LAYER 4 — CROSS-COMMUNITY ANALYSIS (OPTION C)
# ============================================================
community_metrics = (
    df.groupby("Subreddit")
    .agg(
        Total_Posts=("Title", "count"),
        Pain_Count=("Pain_Flag", "sum"),
        Demand_Count=("Demand_Flag", "sum"),
        Cost_Count=("Cost_Flag", "sum"),
        Confusion_Count=("Confusion_Flag", "sum"),
        Avg_Insight_Priority=("Insight_Priority", "mean"),
    )
    .reset_index()
)

for metric in ["Pain", "Demand", "Cost", "Confusion"]:
    community_metrics[f"{metric}_Rate"] = (
        community_metrics[f"{metric}_Count"]
        / community_metrics["Total_Posts"]
    ).round(3)

# ============================================================
# LAYER 5 — INSIGHT VALIDATION SCORE (PERSISTENCE SIGNAL)
# ============================================================
weekly_trends["Signal_Strength"] = (
    weekly_trends["Pain_Count"]
    + weekly_trends["Demand_Count"]
    + weekly_trends["Cost_Count"]
    + weekly_trends["Confusion_Count"]
)

weekly_trends["Signal_Quality"] = weekly_trends["Signal_Strength"].apply(
    lambda x: "High" if x >= 10 else "Medium" if x >= 5 else "Low"
)

# ============================================================
# STREAMLIT UI (SAFE — DOES NOT TOUCH OLD TABS)
# ============================================================
st.subheader("📊 Weekly Trend Analysis (Option B)")
st.dataframe(weekly_trends, use_container_width=True)

st.subheader("🌍 Cross-Community Comparison (Option C)")
st.dataframe(community_metrics, use_container_width=True)

# ============================================================
# EXCEL EXPORT — FULL INTELLIGENCE DATASET
# ============================================================
export_df = df.merge(
    weekly_trends[["Created_Week", "Signal_Quality"]],
    on="Created_Week",
    how="left"
)

st.download_button(
    "⬇️ Download Intelligence Excel",
    export_df.to_excel(index=False),
    file_name="reddit_intelligence_full.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
