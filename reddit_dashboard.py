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

import re
from collections import Counter, defaultdict

STOPWORDS = set([
    "the", "and", "for", "with", "that", "this", "from", "are",
    "was", "were", "have", "has", "had", "you", "your", "about",
    "anyone", "please", "thanks", "help", "using"
])

def clean_text_for_phrases(text: str):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = [t for t in text.split() if t not in STOPWORDS and len(t) > 2]
    return tokens

def extract_phrases(text, n):
    tokens = clean_text_for_phrases(text)
    return [" ".join(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]

def auto_keyword_discovery(df, min_count=3, phrase_lengths=(2, 3)):
    from collections import defaultdict

    phrase_data = defaultdict(list)
    rows = []

    # -------- collect phrases ----------
    for _, row in df.iterrows():
        text = f"{row.get('Title','')} {row.get('Body','')}".lower()

        for n in phrase_lengths:
            words = text.split()
            for i in range(len(words) - n + 1):
                phrase = " ".join(words[i:i+n])
                phrase_data[phrase].append(row)

    # -------- analyze phrases ----------
    for phrase, items in phrase_data.items():
        if len(items) < min_count:
            continue

        pain_pct = sum(i.get("Pain_Flag", 0) for i in items) / len(items) * 100
        demand_pct = sum(i.get("Demand_Flag", 0) for i in items) / len(items) * 100
        avg_priority = sum(i.get("Insight_Priority", 0) for i in items) / len(items)

        rows.append({
            "Phrase": phrase,
            "Posts": len(items),
            "Pain_%": round(pain_pct, 1),
            "Demand_%": round(demand_pct, 1),
            "Avg_Priority": round(avg_priority, 2),
            "Evidence": [i.get("Title", "") for i in items[:5]]
        })

    # -------- final dataframe ----------
    df_out = pd.DataFrame(rows)

    if df_out.empty or "Posts" not in df_out.columns:
        return pd.DataFrame(columns=[
            "Phrase", "Posts", "Pain_%", "Demand_%", "Avg_Priority", "Evidence"
        ])

    return df_out.sort_values("Posts", ascending=False)


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
tab_posts, tab_insights, tab_weekly, tab_analytics, tab_auto = st.tabs(
    ["Posts", "Insights", "Weekly Trends", "Analytics", "Auto-Keyword Discovery"]
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


with tab_auto:
    st.subheader("🧠 Auto-Keyword Discovery")
    st.caption("Discover recurring phrases without predefined keywords")

    col1, col2 = st.columns(2)
    with col1:
        min_count = st.slider("Minimum occurrences", 2, 10, 3)
    with col2:
        phrase_type = st.selectbox(
            "Phrase length",
            options=["2-word", "3-word", "2 & 3-word"]
        )

    if phrase_type == "2-word":
        phrase_lengths = (2,)
    elif phrase_type == "3-word":
        phrase_lengths = (3,)
    else:
        phrase_lengths = (2, 3)

    auto_df = auto_keyword_discovery(
        df,
        min_count=min_count,
        phrase_lengths=phrase_lengths
    )

    if auto_df.empty:
        st.info("No recurring phrases found with current settings.")
        st.stop()

    st.dataframe(
        auto_df[["Phrase", "Posts", "Pain_%", "Demand_%", "Avg_Priority"]],
        use_container_width=True
    )

    # Evidence viewer
    phrase_selected = st.selectbox(
        "Inspect phrase evidence",
        options=auto_df["Phrase"].tolist()
    )

    evidence_rows = auto_df[auto_df["Phrase"] == phrase_selected]["Evidence"].iloc[0]

    st.markdown("### 🔍 Evidence Posts")
    for r in evidence_rows:
        st.markdown(
            f"""
            **r/{r['Subreddit']} | Score {r['Score']}** 
            {r['Title']}
            """
        )


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









