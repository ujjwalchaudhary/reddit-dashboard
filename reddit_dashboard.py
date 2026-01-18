import streamlit as st
import pandas as pd
import praw
from datetime import datetime, timezone
import io

# -------------------------------
# CONFIG
# -------------------------------
st.set_page_config(page_title="Reddit Intelligence Dashboard", layout="wide")

REDDIT_CLIENT_ID = st.secrets["REDDIT_CLIENT_ID"]
REDDIT_CLIENT_SECRET = st.secrets["REDDIT_CLIENT_SECRET"]
REDDIT_USER_AGENT = "reddit-intelligence-dashboard"

SUBREDDITS = ["Rag"]
POST_LIMIT = 100

# -------------------------------
# KEYWORD BUCKETS (Layer 1)
# -------------------------------
KEYWORD_BUCKETS = {
    "pain": [
        "issue", "problem", "bug", "broken", "fails", "failing",
        "hallucination", "slow", "error", "debug", "nightmare"
    ],
    "demand": [
        "how to", "best", "recommend", "suggest", "looking for",
        "anyone used", "need advice", "what is"
    ],
    "cost": [
        "cost", "pricing", "expensive", "cheap", "billing",
        "reduce cost", "optimize"
    ],
    "confusion": [
        "confused", "unclear", "don't understand", "vs", "difference",
        "which one", "help"
    ],
    "sentiment": [
        "love", "great", "awesome", "hate", "bad", "terrible"
    ]
}

# -------------------------------
# REDDIT CLIENT
# -------------------------------
reddit = praw.Reddit(
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    user_agent=REDDIT_USER_AGENT,
)

# -------------------------------
# HELPERS
# -------------------------------
def has_keywords(words, text):
    return int(any(w in text for w in words))

def analyze_post_text(text: str) -> dict:
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
        "Insight_Priority": insight_priority,
    }

def prepare_df_for_excel(df: pd.DataFrame) -> pd.DataFrame:
    """
    Make DataFrame Excel-safe (NO timezone, NO long text crash)
    """
    df = df.copy()

    # Remove timezone info
    for col in df.select_dtypes(include=["datetimetz", "datetime64[ns, UTC]"]).columns:
        df[col] = df[col].dt.tz_localize(None)

    # Truncate long text (Excel limit ≈ 32,767 chars)
    for col in ["Title", "Body"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.slice(0, 32000)

    # Replace NaN / NaT
    df = df.fillna("")

    return df

# -------------------------------
# FETCH DATA
# -------------------------------
@st.cache_data(show_spinner=False)
def fetch_posts():
    rows = []

    for sub in SUBREDDITS:
        subreddit = reddit.subreddit(sub)
        for post in subreddit.hot(limit=POST_LIMIT):
            text = f"{post.title} {post.selftext or ''}"
            analysis = analyze_post_text(text)

            rows.append({
                "Subreddit": sub,
                "Title": post.title,
                "Body": post.selftext,
                "Score": post.score,
                "Comments": post.num_comments,
                "Created_At": datetime.fromtimestamp(post.created_utc, timezone.utc),
                **analysis
            })

    return pd.DataFrame(rows)

# -------------------------------
# UI
# -------------------------------
st.title("📊 Reddit Intelligence Dashboard")

df = fetch_posts()

if df.empty:
    st.warning("No posts fetched.")
    st.stop()

st.success(f"Fetched {len(df)} posts")

# -------------------------------
# INSIGHTS
# -------------------------------
st.subheader("🔥 Top Insight Posts")
top_df = df.sort_values("Insight_Priority", ascending=False).head(10)
st.dataframe(top_df[["Subreddit", "Title", "Body"]], use_container_width=True)

# -------------------------------
# WEEKLY TRENDS (Layer 3)
# -------------------------------
st.subheader("📈 Weekly Trends")

df["Week"] = df["Created_At"].dt.strftime("%Y-W%U")

weekly = (
    df.groupby("Week")
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

st.dataframe(weekly, use_container_width=True)

# -------------------------------
# CROSS-COMMUNITY COMPARISON (Layer 4)
# -------------------------------
st.subheader("🌍 Cross-Community Comparison")

community = (
    df.groupby("Subreddit")
    .agg(
        Total_Posts=("Title", "count"),
        Pain_Rate=("Pain_Flag", "mean"),
        Demand_Rate=("Demand_Flag", "mean"),
        Cost_Rate=("Cost_Flag", "mean"),
        Confusion_Rate=("Confusion_Flag", "mean"),
        Avg_Insight_Priority=("Insight_Priority", "mean"),
    )
    .reset_index()
)

st.dataframe(community, use_container_width=True)

# -------------------------------
# EXCEL EXPORT (FIXED FOREVER)
# -------------------------------
st.subheader("⬇️ Export Data")

safe_df = prepare_df_for_excel(df)

buffer = io.BytesIO()
safe_df.to_excel(buffer, index=False, engine="openpyxl")

st.download_button(
    label="Download Excel",
    data=buffer.getvalue(),
    file_name="reddit_intelligence.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
