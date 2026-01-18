# reddit_dashboard_intelligence.py
import streamlit as st
import praw
import pandas as pd
from datetime import datetime, timezone
import altair as alt
import io

# =====================
# Reddit Configuration
# =====================
CLIENT_ID = "Zw79U9P5jvyND91YLfFlNw"
CLIENT_SECRET = "da_Z-jcrvfUDTojeU82JhZTPynWFYQ"
USER_AGENT = "Myfetchingscript/1.0 by u/ujjwaldrayaan"

reddit = praw.Reddit(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    user_agent=USER_AGENT,
    check_for_async=False
)

# =====================
# Layer 1 — Signal Keywords
# =====================
KEYWORD_BUCKETS = {
    "pain": ["problem", "issue", "broken", "nightmare", "struggling", "fails"],
    "demand": ["how do", "anyone", "need help", "best way", "advice"],
    "cost": ["cost", "pricing", "tokens", "expensive", "billing"],
    "confusion": ["confused", "unclear", "does anyone know"],
    "sentiment": ["love", "hate", "frustrated", "amazing"]
}

# =====================
# Layer 2 — Topic Taxonomy
# =====================
TOPIC_BUCKETS = {
    "retrieval": ["retrieval", "rerank", "bm25", "search"],
    "chunking": ["chunk", "split", "overlap"],
    "evaluation": ["eval", "benchmark", "metrics"],
    "cost": ["cost", "pricing", "tokens"],
    "multimodal": ["image", "pdf", "table", "chart"],
    "infra": ["latency", "scale", "deployment"],
    "prompting": ["prompt", "instruction"],
    "debugging": ["debug", "error", "failing"]
}

# =====================
# Layer 5 — Business Mapping
# =====================
BUSINESS_MAP = {
    "retrieval": "Retrieval optimization tooling",
    "chunking": "Chunking & preprocessing automation",
    "evaluation": "RAG evaluation / benchmarking SaaS",
    "cost": "Cost optimization platform",
    "multimodal": "Multimodal ingestion system",
    "infra": "Scalable RAG infrastructure",
    "prompting": "Prompt management tooling",
    "debugging": "RAG debugging & observability",
    "other": "General RAG enablement"
}

# =====================
# Helper Functions
# =====================
def has_keywords(words, text):
    return int(any(w in text for w in words))

def classify_topic(text):
    for topic, words in TOPIC_BUCKETS.items():
        if any(w in text for w in words):
            return topic
    return "other"

def classify_intent(text):
    if "?" in text or "how do" in text or "anyone" in text:
        return "question"
    if any(w in text for w in ["problem", "issue", "nightmare"]):
        return "complaint"
    if any(w in text for w in ["i built", "we built", "open source"]):
        return "showcase"
    if "benchmark" in text or "vs" in text:
        return "benchmark"
    return "discussion"

def analyze_post_text(text):
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

# =====================
# Fetch Posts
# =====================
def fetch_posts_from_subreddit(
    sub_name, limit, keywords,
    start_date, end_date,
    min_score, min_comments
):
    results = []

    try:
        subreddit = reddit.subreddit(sub_name)

        for post in subreddit.hot(limit=limit):
            created = datetime.fromtimestamp(post.created_utc, timezone.utc)

            if start_date and created.date() < start_date:
                continue
            if end_date and created.date() > end_date:
                continue
            if post.score < min_score or post.num_comments < min_comments:
                continue

            text = f"{post.title or ''} {post.selftext or ''}".lower()

            if keywords and not any(k.lower() in text for k in keywords):
                continue

            analysis = analyze_post_text(text)
            topic = classify_topic(text)
            intent = classify_intent(text)
            week = created.strftime("%Y-%U")

            results.append({
                "Subreddit": sub_name,
                "Title": post.title,
                "Body": post.selftext,
                "Author": str(post.author),
                "Score": post.score,
                "CommentsCount": post.num_comments,
                "Created_UTC": created.strftime("%Y-%m-%d %H:%M:%S"),
                "Week": week,
                "Topic": topic,
                "Intent": intent,
                "Business_Opportunity": BUSINESS_MAP.get(topic),
                "URL": f"https://reddit.com{post.permalink}",
                **analysis
            })

    except Exception as e:
        st.warning(f"⚠️ Skipping r/{sub_name}: {e}")

    return results

# =====================
# Streamlit UI
# =====================
st.set_page_config("Reddit Intelligence Dashboard", layout="wide")
st.title("🔥 Reddit Intelligence Dashboard")

with st.sidebar:
    subreddits = st.text_input("Subreddits", "Rag,ClaudeAI,SaaS").split(",")
    keywords = st.text_input("Keywords", "").split(",")
    limit = st.slider("Posts per subreddit", 10, 300, 100)
    min_score = st.number_input("Min score", 0, 1000, 0)
    min_comments = st.number_input("Min comments", 0, 1000, 0)
    fetch = st.button("🚀 Fetch Data")

posts_df = pd.DataFrame()

if fetch:
    all_posts = []
    for s in subreddits:
        all_posts.extend(
            fetch_posts_from_subreddit(
                s.strip(), limit, keywords,
                None, None, min_score, min_comments
            )
        )

    posts_df = pd.DataFrame(all_posts)

    if not posts_df.empty:
        # Layer 4 — Trend aggregation
        trend = (
            posts_df.groupby(["Week", "Topic"])["Pain_Flag"]
            .sum()
            .reset_index(name="Topic_Pain_Count")
        )
        posts_df = posts_df.merge(trend, on=["Week", "Topic"], how="left")

# =====================
# Display
# =====================
if not posts_df.empty:
    st.subheader("📌 Top Insight Posts")
    st.dataframe(
        posts_df.sort_values("Insight_Priority", ascending=False)
        .reset_index(drop=True)
    )

    st.download_button(
        "📥 Download Excel",
        posts_df.to_excel(index=False),
        file_name="reddit_intelligence.xlsx"
    )
else:
    st.info("Click **Fetch Data** to begin.")
