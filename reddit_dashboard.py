import streamlit as st
import pandas as pd
import re
from collections import defaultdict
from datetime import datetime
from io import BytesIO

# =============================
# PAGE CONFIG
# =============================
st.set_page_config(
    page_title="Reddit Intelligence Dashboard",
    layout="wide"
)

st.title("📊 Reddit Intelligence Dashboard")

# =============================
# SIDEBAR CONTROLS
# =============================
with st.sidebar:
    st.header("⚙️ Controls")

    subreddits_input = st.text_input(
        "Enter subreddits (comma-separated)",
        value="rag"
    )

    posts_per_subreddit = st.slider(
        "Posts per subreddit",
        min_value=10,
        max_value=300,
        value=100,
        step=10
    )

    phrase_len = st.slider(
        "Phrase length",
        min_value=2,
        max_value=4,
        value=2
    )

    min_occurrence = st.slider(
        "Minimum keyword occurrences",
        min_value=2,
        max_value=20,
        value=3
    )

    fetch_btn = st.button("Fetch Data")

# =============================
# SAFE MOCK FETCH (REPLACE LATER WITH PRAW)
# =============================
@st.cache_data(show_spinner=False)
def fetch_posts(subreddits, limit):
    rows = []
    for sub in subreddits:
        for i in range(limit):
            rows.append({
                "Subreddit": sub,
                "Title": f"Sample post {i} about RAG debugging",
                "Body": "I am facing hallucination issues in RAG systems",
                "Created": datetime.now()
            })
    return pd.DataFrame(rows)

# =============================
# TEXT HELPERS
# =============================
def clean_text(text):
    text = text.lower()
    text = re.sub(r"[^a-z\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def extract_phrases(text, n):
    tokens = text.split()
    return [
        " ".join(tokens[i:i+n])
        for i in range(len(tokens) - n + 1)
    ]

# =============================
# AUTO-KEYWORD DISCOVERY (STABLE)
# =============================
def auto_keyword_discovery(df, min_count=3, phrase_len=2):
    if df is None or df.empty:
        return pd.DataFrame()

    phrase_data = defaultdict(list)

    for _, row in df.iterrows():
        text = f"{row.get('Title','')} {row.get('Body','')}"
        text = clean_text(text)

        phrases = extract_phrases(text, phrase_len)
        for p in phrases:
            phrase_data[p].append(1)

    rows = []
    for phrase, items in phrase_data.items():
        if len(items) < min_count:
            continue

        rows.append({
            "Phrase": phrase,
            "Posts": len(items),
            "Pain_%": round(len(items), 2),
            "Demand_%": round(len(items), 2),
            "Avg_Priority": round(len(items), 2)
        })

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).sort_values("Posts", ascending=False)

# =============================
# FETCH DATA
# =============================
df = pd.DataFrame()
auto_df = pd.DataFrame()

if fetch_btn:
    subreddits = [s.strip() for s in subreddits_input.split(",") if s.strip()]
    df = fetch_posts(subreddits, posts_per_subreddit)
    auto_df = auto_keyword_discovery(df, min_occurrence, phrase_len)

    st.success(f"Fetched {len(df)} posts")

# =============================
# MAIN TABS (RESTORED)
# =============================
tab_posts, tab_insights, tab_weekly, tab_analytics, tab_auto = st.tabs([
    "Posts",
    "Insights",
    "Weekly Trends",
    "Analytics",
    "Auto-Keyword Discovery"
])

# =============================
# POSTS TAB
# =============================
with tab_posts:
    st.subheader("📝 All Posts")
    if df.empty:
        st.info("No posts loaded yet.")
    else:
        st.dataframe(df)

# =============================
# INSIGHTS TAB
# =============================
with tab_insights:
    st.subheader("🔥 Top Insight Posts")
    if df.empty:
        st.info("No insights available.")
    else:
        st.dataframe(df.head(10))

# =============================
# WEEKLY TRENDS TAB
# =============================
with tab_weekly:
    st.subheader("📈 Weekly Trends")
    if df.empty:
        st.info("No data for weekly trends.")
    else:
        df_week = df.copy()
        df_week["Week"] = df_week["Created"].dt.strftime("%Y-W%U")
        weekly = df_week.groupby("Week").size().reset_index(name="Total_Posts")
        st.dataframe(weekly)

# =============================
# ANALYTICS TAB
# =============================
with tab_analytics:
    st.subheader("🌍 Cross-Community Analytics")
    if df.empty:
        st.info("No analytics available.")
    else:
        summary = df.groupby("Subreddit").size().reset_index(name="Total_Posts")
        st.dataframe(summary)

# =============================
# AUTO-KEYWORD TAB (SAFE)
# =============================
with tab_auto:
    st.subheader("🔍 Auto-Keyword Discovery")

    if auto_df is None or auto_df.empty:
        st.warning("No auto-keywords discovered.")
    else:
        expected_cols = ["Phrase", "Posts", "Pain_%", "Demand_%", "Avg_Priority"]
        safe_cols = [c for c in expected_cols if c in auto_df.columns]

        if not safe_cols:
            st.warning("Auto-keyword data incomplete.")
            st.dataframe(auto_df)
        else:
            st.dataframe(auto_df[safe_cols])

# =============================
# EXPORT (SAFE EXCEL)
# =============================
st.markdown("---")
st.subheader("⬇️ Export Data")

if not df.empty:
    buffer = BytesIO()
    safe_df = df.copy()
    safe_df = safe_df.applymap(lambda x: str(x) if isinstance(x, (list, dict)) else x)

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        safe_df.to_excel(writer, index=False, sheet_name="Posts")

    st.download_button(
        "Download Excel",
        data=buffer.getvalue(),
        file_name="reddit_data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("Nothing to export yet.")
