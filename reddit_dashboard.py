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
# REDDIT CONFIG (HARDCODED – AS REQUESTED)
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
# SIDEBAR CONTROLS
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

keyword_input = st.sidebar.text_input(
    "Filter posts by keywords (optional, comma-separated)",
    value=""
)

SUBREDDITS = [s.strip() for s in subreddit_input.split(",") if s.strip()]
KEYWORDS = [k.strip().lower() for k in keyword_input.split(",") if k.strip()]

# =========================================================
# KEYWORD BUCKETS (ANALYSIS LAYER)
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
def has_keywords(words, text):
    return int(any(w in text for w in words))

def analyze_text(text: str) -> dict:
    text = (text or "").lower()

    pain = has_keywords(KEYWORD_BUCKETS["pain"], text)
    demand = has_keywords(KEYWORD_BUCKETS["demand"], text)
    cost = has_keywords(KEYWORD_BUCKETS["cost"], text)
    confusion = has_keywords(KEYWORD_BUCKETS["confusion"], text)
    sentiment = has_keywords(KEYWORD_BUCKETS["sentiment"], text)

    insight_priority = (pain * 2) + (demand * 2) + cost + confusion + sentiment

    return {
        "Pain_Flag": pain,
        "Demand_Flag": demand,
        "Cost_Flag": cost,
        "Confusion_Flag": confusion,
        "Sentiment_Flag": sentiment,
        "Insight_Priority": insight_priority
    }

# =========================================================
# FETCH POSTS (WITH KEYWORD PRE-FILTER RESTORED)
# =========================================================
@st.cache_data(show_spinner=False)
def fetch_posts(subreddits, limit, keywords):
    rows = []

    for sub in subreddits:
        try:
            subreddit = reddit.subreddit(sub)
            for post in subreddit.hot(limit=limit):
                text = f"{post.title or ''} {post.selftext or ''}"
                text_lower = text.lower()

                # 🔍 KEYWORD-BASED EXTRACTION (RESTORED FEATURE)
                if keywords:
                    if not any(k in text_lower for k in keywords):
                        continue

                analysis = analyze_text(text)

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
        except Exception as e:
            st.warning(f"Skipping r/{sub}: {e}")

    return pd.DataFrame(rows)

# =========================================================
# LOAD DATA
# =========================================================
if not SUBREDDITS:
    st.error("Please enter at least one subreddit.")
    st.stop()

with st.spinner("Fetching and analyzing Reddit posts..."):
    df = fetch_posts(SUBREDDITS, POST_LIMIT, KEYWORDS)

if df.empty:
    st.warning("No posts matched your criteria.")
    st.stop()

st.success(f"Fetched {len(df)} posts")

# =========================================================
# TABS
# =========================================================
tab_posts, tab_insights, tab_weekly, tab_analytics = st.tabs(
    ["Posts", "Insights", "Weekly Trends", "Analytics"]
)

# =========================================================
# POSTS TAB
# =========================================================
with tab_posts:
    st.subheader("📄 All Posts")
    st.dataframe(
        df[["Subreddit", "Title", "Body", "Score", "Comments"]],
        use_container_width=True
    )

# =========================================================
# INSIGHTS TAB
# =========================================================
with tab_insights:
    st.subheader("🔥 Top Insight Posts")

    top_df = df.sort_values(
        "Insight_Priority", ascending=False
    ).head(10)

    st.dataframe(
        top_df[
            ["Subreddit", "Title",
             "Pain_Flag", "Demand_Flag",
             "Cost_Flag", "Confusion_Flag",
             "Insight_Priority"]
        ],
        use_container_width=True
    )

# =========================================================
# WEEKLY TRENDS TAB
# =========================================================
with tab_weekly:
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

    analytics = df.groupby("Subreddit").agg(
        Total_Posts=("Title", "count"),
        Pain_Rate=("Pain_Flag", "mean"),
        Demand_Rate=("Demand_Flag", "mean"),
        Cost_Rate=("Cost_Flag", "mean"),
        Confusion_Rate=("Confusion_Flag", "mean"),
        Avg_Insight_Priority=("Insight_Priority", "mean")
    ).reset_index()

    st.dataframe(analytics, use_container_width=True)

# =========================================================
# EXPORT (SAFE)
# =========================================================
st.subheader("⬇️ Export Data")

export_df = df.copy()
export_df["Created_UTC"] = export_df["Created_UTC"].astype(str)

buffer = io.BytesIO()
export_df.to_excel(buffer, index=False)
buffer.seek(0)

st.download_button(
    "Download Excel",
    buffer,
    file_name="reddit_intelligence_export.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
