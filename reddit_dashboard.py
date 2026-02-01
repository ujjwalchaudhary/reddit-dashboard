# =========================================================
# Reddit Intelligence Dashboard (FINAL – STABLE)
# =========================================================

import streamlit as st
import pandas as pd
import praw
from collections import defaultdict, Counter
from datetime import datetime, timezone
import re

# =========================================================
# CONFIG
# =========================================================
st.set_page_config(
    page_title="Reddit Intelligence Dashboard",
    layout="wide"
)

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
# KEYWORD BUCKETS (Layer 1)
# =========================================================
KEYWORD_BUCKETS = {
    "pain": [
        "problem", "issue", "bug", "broken", "fails", "error",
        "slow", "hallucination", "debug", "nightmare"
    ],
    "demand": [
        "how to", "best", "recommend", "suggest", "looking for",
        "anyone used", "need advice"
    ],
    "cost": [
        "cost", "pricing", "expensive", "cheap", "billing",
        "reduce cost"
    ],
    "confusion": [
        "confused", "unclear", "don't understand",
        "vs", "difference", "which one"
    ],
}

# =========================================================
# HELPERS
# =========================================================
def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def has_keywords(text: str, keywords) -> int:
    return int(any(k in text for k in keywords))


# =========================================================
# FETCH POSTS
# =========================================================
@st.cache_data(show_spinner=False)
def fetch_posts(subreddits, limit):
    rows = []

    for sub in subreddits:
        subreddit = reddit.subreddit(sub.strip())
        for post in subreddit.hot(limit=limit):
            text = f"{post.title} {post.selftext}"
            text_clean = clean_text(text)

            pain = has_keywords(text_clean, KEYWORD_BUCKETS["pain"])
            demand = has_keywords(text_clean, KEYWORD_BUCKETS["demand"])
            cost = has_keywords(text_clean, KEYWORD_BUCKETS["cost"])
            confusion = has_keywords(text_clean, KEYWORD_BUCKETS["confusion"])

            insight_priority = pain * 2 + demand * 2 + cost + confusion

            rows.append({
                "Subreddit": sub,
                "Title": post.title,
                "Body": post.selftext,
                "Score": post.score,
                "Comments": post.num_comments,
                "Created": datetime.fromtimestamp(post.created_utc, tz=timezone.utc),
                "Pain": pain,
                "Demand": demand,
                "Cost": cost,
                "Confusion": confusion,
                "Insight_Priority": insight_priority
            })

    return pd.DataFrame(rows)


# =========================================================
# AUTO-KEYWORD DISCOVERY (SAFE)
# =========================================================
def auto_keyword_discovery(df, min_count=3, phrase_lengths=(2, 3)):
    if df is None or df.empty:
        return pd.DataFrame()

    phrase_map = defaultdict(list)

    for _, row in df.iterrows():
        text = clean_text(f"{row['Title']} {row['Body']}")
        tokens = text.split()

        for n in phrase_lengths:
            for i in range(len(tokens) - n + 1):
                phrase = " ".join(tokens[i:i+n])
                phrase_map[phrase].append(row)

    rows = []
    for phrase, items in phrase_map.items():
        if len(items) < min_count:
            continue

        pain_pct = sum(i["Pain"] for i in items) / len(items) * 100
        demand_pct = sum(i["Demand"] for i in items) / len(items) * 100
        avg_priority = sum(i["Insight_Priority"] for i in items) / len(items)

        rows.append({
            "Phrase": phrase,
            "Posts": len(items),
            "Pain_%": round(pain_pct, 1),
            "Demand_%": round(demand_pct, 1),
            "Avg_Priority": round(avg_priority, 2),
        })

    return pd.DataFrame(rows).sort_values("Posts", ascending=False)


# =========================================================
# WEEKLY TRENDS
# =========================================================
def weekly_trends(df):
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()
    df["Week"] = df["Created"].dt.strftime("%Y-W%U")

    agg = df.groupby("Week").agg(
        Total_Posts=("Title", "count"),
        Pain_Count=("Pain", "sum"),
        Demand_Count=("Demand", "sum"),
        Cost_Count=("Cost", "sum"),
        Confusion_Count=("Confusion", "sum"),
        Avg_Insight_Priority=("Insight_Priority", "mean")
    ).reset_index()

    return agg.sort_values("Week")


# =========================================================
# SIDEBAR CONTROLS
# =========================================================
st.sidebar.header("Controls")

subreddits_input = st.sidebar.text_input(
    "Enter subreddits (comma-separated)",
    value="Rag"
)

post_limit = st.sidebar.slider(
    "Posts per subreddit",
    10, 300, 100
)

min_phrase_count = st.sidebar.slider(
    "Auto-keyword minimum occurrences",
    2, 10, 3
)

# =========================================================
# MAIN
# =========================================================
subreddits = [s.strip() for s in subreddits_input.split(",") if s.strip()]

df = fetch_posts(subreddits, post_limit)

st.success(f"Fetched {len(df)} posts")

tabs = st.tabs(["Posts", "Insights", "Weekly Trends", "Auto-Keyword Discovery"])

# ---------------- POSTS TAB ----------------
with tabs[0]:
    st.subheader("All Posts")
    st.dataframe(df)

# ---------------- INSIGHTS TAB ----------------
with tabs[1]:
    st.subheader("Top Insight Posts")
    top = df.sort_values("Insight_Priority", ascending=False).head(20)
    st.dataframe(top[[
        "Subreddit", "Title", "Pain", "Demand",
        "Cost", "Confusion", "Insight_Priority"
    ]])

# ---------------- WEEKLY TRENDS TAB ----------------
with tabs[2]:
    st.subheader("Weekly Trends")
    weekly_df = weekly_trends(df)
    st.dataframe(weekly_df)

# ---------------- AUTO-KEYWORD TAB ----------------
with tabs[3]:
    st.subheader("Auto-Keyword Discovery")

    auto_df = auto_keyword_discovery(
        df,
        min_count=min_phrase_count
    )

    if auto_df is None or auto_df.empty:
        st.warning("No auto-keywords discovered.")
    else:
        expected_cols = ["Phrase", "Posts", "Pain_%", "Demand_%", "Avg_Priority"]
        missing = [c for c in expected_cols if c not in auto_df.columns]

        if missing:
            st.warning(f"Missing columns: {missing}")
            st.dataframe(auto_df)
        else:
            st.dataframe(auto_df[expected_cols])
import io

# ---------------- EXPORT ----------------
st.subheader("Export Data")

if df is None or df.empty:
    st.warning("No data available to export.")
else:
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)

    st.download_button(
        label="Download Excel",
        data=buffer,
        file_name="reddit_intelligence.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
