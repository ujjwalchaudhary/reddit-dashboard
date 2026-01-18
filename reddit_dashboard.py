# =========================
# Reddit Dashboard (LOCKED)
# =========================

import streamlit as st
import praw
import pandas as pd
from datetime import datetime, timezone
import altair as alt
import io

# -------------------------
# Reddit Credentials
# -------------------------
CLIENT_ID = "Zw79U9P5jvyND91YLfFlNw"
CLIENT_SECRET = "da_Z-jcrvfUDTojeU82JhZTPynWFYQ"
USER_AGENT = "Myfetchingscript/1.0 by u/ujjwaldrayaan"

reddit = praw.Reddit(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    user_agent=USER_AGENT,
    check_for_async=False
)

# -------------------------
# Keyword Buckets
# -------------------------
KEYWORD_BUCKETS = {
    "pain": [
        "problem", "issue", "stuck", "failing", "broken",
        "doesn't work", "error", "limitation", "hard to"
    ],
    "demand": [
        "need", "looking for", "recommend", "any alternative",
        "best way", "solution", "how do i"
    ],
    "cost": [
        "price", "cost", "expensive", "cheap",
        "billing", "roi", "worth it"
    ],
    "confusion": [
        "confused", "unsure", "which one", "vs",
        "difference", "compare"
    ],
    "sentiment": [
        "frustrated", "disappointed", "love",
        "hate", "terrible", "amazing"
    ]
}

# -------------------------
# Text Analysis (SAFE)
# -------------------------
def analyze_post_text(text: str) -> dict:
    text = (text or "").lower()

    def has_keywords(words):
        return int(any(w in text for w in words))

    pain = has_keywords(KEYWORD_BUCKETS["pain"])
    demand = has_keywords(KEYWORD_BUCKETS["demand"])
    cost = has_keywords(KEYWORD_BUCKETS["cost"])
    confusion = has_keywords(KEYWORD_BUCKETS["confusion"])
    sentiment = has_keywords(KEYWORD_BUCKETS["sentiment"])

    insight_priority = (pain * 2) + (demand * 2) + cost + confusion + sentiment

    return {
        "Pain_Flag": pain,
        "Demand_Flag": demand,
        "Cost_Flag": cost,
        "Confusion_Flag": confusion,
        "Sentiment_Flag": sentiment,
        "Insight_Priority": insight_priority
    }

# -------------------------
# Fetch Posts (LOCKED)
# -------------------------
def fetch_posts_from_subreddit(
    sub_name: str,
    limit: int,
    keywords,
    start_date,
    end_date,
    min_score,
    min_comments
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

            text = (post.title or "") + " " + (post.selftext or "")
            text_lower = text.lower()

            if keywords:
                if not any(k.lower() in text_lower for k in keywords):
                    continue

            if post.score < min_score or post.num_comments < min_comments:
                continue

            comments_preview = ""
            try:
                post.comments.replace_more(limit=0)
                top_comments = [
                    c.body.strip().replace("\n", " ")
                    for c in post.comments[:2]
                ]
                comments_preview = " | ".join(top_comments)
            except Exception:
                comments_preview = ""

            analysis = analyze_post_text(text)

            results.append({
                "Subreddit": sub_name,
                "Title": post.title or "",
                "Body": post.selftext or "",
                "Author": str(post.author),
                "Score": post.score,
                "CommentsCount": post.num_comments,
                "TopComments": comments_preview,
                "Created_UTC": created.strftime("%Y-%m-%d %H:%M:%S"),
                "URL": f"https://reddit.com{post.permalink}",
                **analysis
            })

    except Exception as e:
        st.warning(f"⚠️ Skipping r/{sub_name}: {e}")

    return results

# -------------------------
# Excel Export
# -------------------------
def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="posts")
    return buf.getvalue()

# =========================
# Streamlit UI
# =========================
st.set_page_config(page_title="Reddit Intelligence Dashboard", layout="wide")
st.title("📊 Reddit Intelligence Dashboard")

with st.sidebar:
    st.header("Fetch Options")
    sub_input = st.text_input("Subreddits", "SaaS, startups, ProductManagement")
    subreddits = [s.strip() for s in sub_input.split(",") if s.strip()]

    kw_input = st.text_input("Keywords (optional)", "")
    keywords = [k.strip() for k in kw_input.split(",") if k.strip()]

    start_date = st.date_input("Start date", value=None)
    end_date = st.date_input("End date", value=None)

    limit = st.slider("Posts per subreddit", 10, 300, 100)
    min_score = st.number_input("Min score", 0, 1000, 0)
    min_comments = st.number_input("Min comments", 0, 1000, 0)

    fetch_btn = st.button("🚀 Fetch Posts")

posts_df = pd.DataFrame()

if fetch_btn:
    all_posts = []
    for sub in subreddits:
        all_posts.extend(
            fetch_posts_from_subreddit(
                sub,
                limit,
                keywords,
                start_date,
                end_date,
                min_score,
                min_comments
            )
        )
    posts_df = pd.DataFrame(all_posts)

tabs = st.tabs(["Posts", "Insights", "Analytics"])

# -------------------------
# Posts Tab
# -------------------------
with tabs[0]:
    if not posts_df.empty:
        st.dataframe(posts_df)
        st.download_button(
            "⬇️ Download Excel",
            df_to_excel_bytes(posts_df),
            "reddit_posts.xlsx"
        )
    else:
        st.info("No data yet.")

# -------------------------
# Insights Tab
# -------------------------
with tabs[1]:
    if not posts_df.empty:
        top = posts_df.sort_values("Insight_Priority", ascending=False).head(10)
        st.subheader("🔥 Top Insight Posts")
        st.dataframe(
            top[
                [
                    "Subreddit",
                    "Title",
                    "Insight_Priority",
                    "Pain_Flag",
                    "Demand_Flag",
                    "Cost_Flag",
                    "Confusion_Flag"
                ]
            ]
        )

# -------------------------
# Analytics Tab
# -------------------------
with tabs[2]:
    if not posts_df.empty:
        count_df = posts_df["Subreddit"].value_counts().reset_index()
        count_df.columns = ["Subreddit", "Count"]

        chart = alt.Chart(count_df).mark_bar().encode(
            x="Subreddit:N",
            y="Count:Q"
        )
        st.altair_chart(chart, use_container_width=True) 








