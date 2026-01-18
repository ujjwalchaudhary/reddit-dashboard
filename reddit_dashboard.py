import streamlit as st
import praw
import pandas as pd
from datetime import datetime, timezone
import io

# =====================================================
# REDDIT CONFIG
# =====================================================
CLIENT_ID = "Zw79U9P5jvyND91YLfFlNw"
CLIENT_SECRET = "da_Z-jcrvfUDTojeU82JhZTPynWFYQ"
USER_AGENT = "Myfetchingscript/1.0 by u/ujjwaldrayaan"

reddit = praw.Reddit(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    user_agent=USER_AGENT,
    check_for_async=False
)

# =====================================================
# KEYWORD BUCKETS (LAYER 1)
# =====================================================
KEYWORD_BUCKETS = {
    "pain": ["problem", "issue", "broken", "nightmare", "struggling", "fails"],
    "demand": ["how do", "anyone", "need help", "best way", "advice"],
    "cost": ["cost", "pricing", "tokens", "expensive", "billing"],
    "confusion": ["confused", "unclear", "does anyone know"],
    "sentiment": ["love", "hate", "frustrated", "amazing"]
}

# =====================================================
# ANALYSIS FUNCTIONS
# =====================================================
def analyze_post_text(text: str) -> dict:
    text = (text or "").lower()

    def hit(words):
        return int(any(w in text for w in words))

    pain = hit(KEYWORD_BUCKETS["pain"])
    demand = hit(KEYWORD_BUCKETS["demand"])
    cost = hit(KEYWORD_BUCKETS["cost"])
    confusion = hit(KEYWORD_BUCKETS["confusion"])
    sentiment = hit(KEYWORD_BUCKETS["sentiment"])

    insight_priority = (pain * 2) + (demand * 2) + cost + confusion + sentiment

    return {
        "Pain_Flag": pain,
        "Demand_Flag": demand,
        "Cost_Flag": cost,
        "Confusion_Flag": confusion,
        "Sentiment_Flag": sentiment,
        "Insight_Priority": insight_priority
    }

# =====================================================
# FETCH REDDIT POSTS
# =====================================================
def fetch_posts(subreddit, limit):
    rows = []

    try:
        sub = reddit.subreddit(subreddit)
        for post in sub.hot(limit=limit):
            created = datetime.fromtimestamp(post.created_utc, timezone.utc)

            text = f"{post.title or ''} {post.selftext or ''}"
            analysis = analyze_post_text(text)

            rows.append({
                "Subreddit": subreddit,
                "Title": post.title,
                "Body": post.selftext,
                "Score": post.score,
                "Comments": post.num_comments,
                "Created_At": created,
                **analysis
            })

    except Exception as e:
        st.warning(f"Skipping r/{subreddit}: {e}")

    return rows

# =====================================================
# STREAMLIT UI
# =====================================================
st.set_page_config(page_title="Reddit Intelligence Dashboard", layout="wide")
st.title("📊 Reddit Intelligence Dashboard")

with st.sidebar:
    subs = st.text_input("Subreddits (comma separated)", "RAG,ClaudeAI,SaaS")
    limit = st.slider("Posts per subreddit", 10, 300, 100)
    fetch_btn = st.button("🚀 Fetch Posts")

df = None  # SAFE INITIALIZATION

# =====================================================
# DATA FETCH
# =====================================================
if fetch_btn:
    all_rows = []
    for s in [x.strip() for x in subs.split(",") if x.strip()]:
        all_rows.extend(fetch_posts(s, limit))

    if all_rows:
        df = pd.DataFrame(all_rows)
        st.success(f"Fetched {len(df)} posts")
    else:
        st.warning("No data fetched")

# =====================================================
# ANALYSIS (ONLY IF DATA EXISTS)
# =====================================================
if df is not None and not df.empty:

    # ---------- Layer 2: Time ----------
    df["Year"] = df["Created_At"].dt.isocalendar().year
    df["Week"] = (
        df["Created_At"].dt.isocalendar().year.astype(str)
        + "-W"
        + df["Created_At"].dt.isocalendar().week.astype(str)
    )

    # ---------- Layer 3: Weekly Trends ----------
    weekly = (
        df.groupby("Week")
        .agg(
            Total_Posts=("Title", "count"),
            Pain_Count=("Pain_Flag", "sum"),
            Demand_Count=("Demand_Flag", "sum"),
            Cost_Count=("Cost_Flag", "sum"),
            Confusion_Count=("Confusion_Flag", "sum"),
            Avg_Insight_Priority=("Insight_Priority", "mean")
        )
        .reset_index()
    )

    # ---------- Layer 4: Cross-Community ----------
    community = (
        df.groupby("Subreddit")
        .agg(
            Total_Posts=("Title", "count"),
            Pain_Rate=("Pain_Flag", "mean"),
            Demand_Rate=("Demand_Flag", "mean"),
            Cost_Rate=("Cost_Flag", "mean"),
            Confusion_Rate=("Confusion_Flag", "mean"),
            Avg_Insight_Priority=("Insight_Priority", "mean")
        )
        .reset_index()
    )

    # =====================================================
    # DISPLAY
    # =====================================================
    st.subheader("🔥 Top Insight Posts")
    st.dataframe(
        df.sort_values("Insight_Priority", ascending=False),
        use_container_width=True
    )

    st.subheader("📈 Weekly Trends")
    st.dataframe(weekly, use_container_width=True)

    st.subheader("🌍 Cross-Community Comparison")
    st.dataframe(community, use_container_width=True)

    # =====================================================
    # EXPORT
    # =====================================================
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)
    st.download_button(
        "⬇️ Download Excel",
        buffer.getvalue(),
        file_name="reddit_intelligence.xlsx"
    )

else:
    st.info("Fetch data to begin analysis.")
