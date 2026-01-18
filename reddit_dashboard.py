import streamlit as st
import pandas as pd
import praw
from datetime import datetime, timezone
import io

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="Reddit Intelligence Dashboard",
    layout="wide"
)

# =========================================================
# REDDIT CONFIG (HARDCODED AS REQUESTED)
# =========================================================
CLIENT_ID = "Zw79U9P5jvyND91YLfFlNw"
CLIENT_SECRET = "da_Z-jcrvfUDTojeU82JhZTPynWFYQ"
USER_AGENT = "Myfetchingscript/1.0 by u/ujjwaldrayaan"

reddit = praw.Reddit(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    user_agent=USER_AGENT,
    check_for_async=False
)

# =========================================================
# SIDEBAR CONTROLS (RESTORED ✅)
# =========================================================
st.sidebar.header("🔧 Controls")

subreddit_input = st.sidebar.text_input(
    "Enter subreddits (comma-separated)",
    value="Rag"
)

POST_LIMIT = st.sidebar.slider(
    "Posts per subreddit",
    min_value=10,
    max_value=300,
    value=100,
    step=10
)

SUBREDDITS = [s.strip() for s in subreddit_input.split(",") if s.strip()]

# =========================================================
# KEYWORD BUCKETS (LAYER 1)
# =========================================================
KEYWORD_BUCKETS = {
    "pain": [
        "issue", "problem", "bug", "broken", "fails",
        "hallucination", "slow", "error", "debug", "nightmare"
    ],
    "demand": [
        "how to", "best", "recommend", "suggest",
        "looking for", "anyone used", "need advice"
    ],
    "cost": [
        "cost", "pricing", "expensive", "cheap",
        "billing", "reduce cost"
    ],
    "confusion": [
        "confused", "unclear", "don't understand",
        "vs", "difference", "which one"
    ],
    "sentiment": [
        "love", "great", "awesome", "hate", "bad", "terrible"
    ]
}

# =========================================================
# HELPERS
# =========================================================
def has_keywords(text: str, keywords: list) -> int:
    if not text:
        return 0
    text = text.lower()
    return int(any(k in text for k in keywords))

def analyze_post(text: str) -> dict:
    pain = has_keywords(text, KEYWORD_BUCKETS["pain"])
    demand = has_keywords(text, KEYWORD_BUCKETS["demand"])
    cost = has_keywords(text, KEYWORD_BUCKETS["cost"])
    confusion = has_keywords(text, KEYWORD_BUCKETS["confusion"])
    sentiment = has_keywords(text, KEYWORD_BUCKETS["sentiment"])

    insight_priority = (
        pain * 2 +
        demand * 2 +
        cost +
        confusion +
        sentiment
    )

    return {
        "Pain_Flag": pain,
        "Demand_Flag": demand,
        "Cost_Flag": cost,
        "Confusion_Flag": confusion,
        "Sentiment_Flag": sentiment,
        "Insight_Priority": insight_priority
    }

# =========================================================
# FETCH POSTS
# =========================================================
@st.cache_data(show_spinner=False)
def fetch_posts(subreddits, limit):
    rows = []

    for sub in subreddits:
        subreddit = reddit.subreddit(sub)
        for post in subreddit.hot(limit=limit):
            text = f"{post.title or ''} {post.selftext or ''}"
            analysis = analyze_post(text)

            rows.append({
                "Subreddit": sub,
                "Title": post.title,
                "Body": post.selftext,
                "Score": post.score,
                "Comments": post.num_comments,
                "Created_UTC": datetime.fromtimestamp(
                    post.created_utc, tz=timezone.utc
                ),
                **analysis
            })

    return pd.DataFrame(rows)

# =========================================================
# MAIN APP
# =========================================================
st.title("📊 Reddit Intelligence Dashboard")

if not SUBREDDITS:
    st.warning("Please enter at least one subreddit.")
    st.stop()

with st.spinner("Fetching and analyzing Reddit posts..."):
    df = fetch_posts(SUBREDDITS, POST_LIMIT)

if df.empty:
    st.warning("No posts found.")
    st.stop()

st.success(f"Fetched {len(df)} posts")

# =========================================================
# TABS
# =========================================================
tab_posts, tab_insights, tab_analytics = st.tabs(
    ["Posts", "Insights", "Analytics"]
)

# =========================================================
# POSTS TAB
# =========================================================
with tab_posts:
    st.subheader("All Posts")
    st.dataframe(df, use_container_width=True)

# =========================================================
# INSIGHTS TAB
# =========================================================
with tab_insights:
    st.subheader("🔥 Top Insight Posts")

    top_df = df.sort_values(
        "Insight_Priority", ascending=False
    ).head(15)

    st.dataframe(
        top_df[
            ["Subreddit", "Title", "Body",
             "Pain_Flag", "Demand_Flag",
             "Cost_Flag", "Confusion_Flag",
             "Insight_Priority"]
        ],
        use_container_width=True
    )

    # -------------------------------
    # WEEKLY TRENDS (OPTION B + C)
    # -------------------------------
    st.subheader("📈 Weekly Trends")

    df["Week"] = df["Created_UTC"].dt.strftime("%Y-W%U")

    weekly = df.groupby("Week").agg(
        Total_Posts=("Title", "count"),
        Pain_Count=("Pain_Flag", "sum"),
        Demand_Count=("Demand_Flag", "sum"),
        Cost_Count=("Cost_Flag", "sum"),
        Confusion_Count=("Confusion_Flag", "sum"),
        Avg_Insight_Priority=("Insight_Priority", "mean")
    ).reset_index()

    st.dataframe(weekly, use_container_width=True)

# =========================================================
# ANALYTICS TAB
# =========================================================
with tab_analytics:
    st.subheader("🌍 Cross-Community Comparison")

    community = df.groupby("Subreddit").agg(
        Total_Posts=("Title", "count"),
        Pain_Rate=("Pain_Flag", "mean"),
        Demand_Rate=("Demand_Flag", "mean"),
        Cost_Rate=("Cost_Flag", "mean"),
        Confusion_Rate=("Confusion_Flag", "mean"),
        Avg_Insight_Priority=("Insight_Priority", "mean")
    ).reset_index()

    st.dataframe(community, use_container_width=True)

# =========================================================
# EXPORT (SAFE EXCEL)
# =========================================================
st.subheader("⬇️ Export Data")

export_df = df.copy()

# Make Excel-safe (critical fix)
for col in export_df.columns:
    export_df[col] = export_df[col].astype(str)

buffer = io.BytesIO()
export_df.to_excel(buffer, index=False)
buffer.seek(0)

st.download_button(
    label="Download Excel",
    data=buffer,
    file_name="reddit_intelligence_export.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
