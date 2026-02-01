# ===============================
# REDDIT INTELLIGENCE DASHBOARD
# SAFE, STABLE, SINGLE FILE
# ===============================

import streamlit as st
import pandas as pd
import praw
import re
import io
from collections import defaultdict
from datetime import datetime

# ===============================
# CONFIG
# ===============================

CLIENT_ID = "Zw79U9P5jvyND91YLfFlNw"
CLIENT_SECRET = "da_Z-jcrvfUDTojeU82JhZTPynWFYQ"
USER_AGENT = "Myfetchingscript/1.0 by u/ujjwaldrayaan"

# ===============================
# REDDIT CLIENT
# ===============================

reddit = praw.Reddit(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    user_agent=USER_AGENT
)

# ===============================
# UTILS
# ===============================

def clean_text(text):
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_phrases(text, n=2):
    tokens = clean_text(text).split()
    return [" ".join(tokens[i:i+n]) for i in range(len(tokens)-n+1)]


def make_excel_safe(df):
    df = df.copy()
    for col in df.columns:
        df[col] = df[col].apply(
            lambda x: ", ".join(map(str, x)) if isinstance(x, (list, tuple, set))
            else str(x) if isinstance(x, dict)
            else x
        )
    return df


# ===============================
# FETCH POSTS
# ===============================

@st.cache_data(show_spinner=False)
def fetch_posts(subreddits, limit):
    rows = []

    for sub in subreddits:
        try:
            for post in reddit.subreddit(sub).hot(limit=limit):
                rows.append({
                    "Subreddit": sub,
                    "Title": post.title,
                    "Body": post.selftext,
                    "Score": post.score,
                    "Comments": post.num_comments,
                    "Created": datetime.fromtimestamp(post.created_utc)
                })
        except Exception as e:
            st.warning(f"Failed to fetch r/{sub}: {e}")

    return pd.DataFrame(rows)


# ===============================
# AUTO KEYWORD DISCOVERY
# ===============================

def auto_keyword_discovery(df, min_count=3, phrase_len=2):
    if df is None or df.empty:
        return pd.DataFrame()

    phrase_map = defaultdict(list)

    for _, row in df.iterrows():
        text = f"{row.get('Title','')} {row.get('Body','')}"
        for phrase in extract_phrases(text, phrase_len):
            phrase_map[phrase].append(row)

    rows = []
    for phrase, items in phrase_map.items():
        if len(items) < min_count:
            continue

        rows.append({
            "Phrase": phrase,
            "Posts": len(items),
            "Pain_%": round(len(items) / max(len(df), 1) * 100, 1),
            "Demand_%": round(sum(i.get("Score", 0) > 10 for i in items) / len(items) * 100, 1),
            "Avg_Priority": round(sum(i.get("Score", 0) for i in items) / len(items), 2),
            "Evidence": [i.get("Title", "") for i in items[:5]]
        })

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).sort_values("Posts", ascending=False)


# ===============================
# UI
# ===============================

st.set_page_config(page_title="Reddit Intelligence", layout="wide")
st.title("📊 Reddit Intelligence Dashboard")

with st.sidebar:
    subs = st.text_input("Subreddits (comma separated)", "rag")
    limit = st.slider("Posts per subreddit", 10, 200, 100)
    min_count = st.slider("Minimum keyword occurrences", 2, 10, 3)
    phrase_len = st.selectbox("Phrase length", [2, 3])

    fetch_btn = st.button("Fetch Data")

# ===============================
# MAIN LOGIC
# ===============================

df = None
auto_df = None

if fetch_btn:
    sub_list = [s.strip() for s in subs.split(",") if s.strip()]
    df = fetch_posts(sub_list, limit)

    if df.empty:
        st.warning("No posts fetched.")
    else:
        st.success(f"Fetched {len(df)} posts")

        auto_df = auto_keyword_discovery(df, min_count, phrase_len)

# ===============================
# DISPLAY POSTS
# ===============================

if df is not None and not df.empty:
    st.subheader("Posts")
    st.dataframe(df)

# ===============================
# SAFE AUTO KEYWORD DISPLAY
# ===============================

st.subheader("Auto-Keyword Discovery")

if auto_df is None or auto_df.empty:
    st.warning("No auto-keywords discovered for current selection.")
else:
    expected_cols = ["Phrase", "Posts", "Pain_%", "Demand_%", "Avg_Priority"]
    missing = [c for c in expected_cols if c not in auto_df.columns]

    if missing:
        st.warning(f"Missing columns: {missing}")
        st.dataframe(auto_df)
    else:
        st.dataframe(auto_df[expected_cols])

# ===============================
# EXPORT
# ===============================

st.subheader("Export")

if df is not None and not df.empty:
    safe_df = make_excel_safe(df)
    buffer = io.BytesIO()
    safe_df.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)

    st.download_button(
        "Download Excel",
        buffer,
        "reddit_intelligence.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
