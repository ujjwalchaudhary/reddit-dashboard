# reddit_dashboard_upgraded.py
import streamlit as st
import praw
import pandas as pd
from datetime import datetime, timezone
import altair as alt
import io

# ---------- Keyword Buckets ----------
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

# --- Configure your Reddit credentials here ---
CLIENT_ID = "Zw79U9P5jvyND91YLfFlNw"
CLIENT_SECRET = "da_Z-jcrvfUDTojeU82JhZTPynWFYQ"
USER_AGENT = "Myfetchingscript/1.0 by u/ujjwaldrayaan"

reddit = praw.Reddit(
    client_id="Zw79U9P5jvyND91YLfFlNw",
    client_secret="da_Z-jcrvfUDTojeU82JhZTPynWFYQ",
    user_agent="Myfetchingscript/1.0 by u/ujjwaldrayaan",
    check_for_async=False
)

# ---------- Helper functions ----------
def fetch_posts_from_subreddit(sub_name: str, limit: int, keywords, start_date, end_date, min_score, min_comments):
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

            # top comments (optional short preview)
            comments_preview = ""
            try:
                post.comments.replace_more(limit=0)
                top_comments = [c.body.strip().replace("\n", " ") for c in post.comments[:2]]
                comments_preview = " | ".join(top_comments)
            except Exception:
                comments_preview = ""

            full_text = f"{post.title or ''} {post.selftext or ''}"
analysis = analyze_post_text(full_text)

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

    # 🔥 Analysis columns
    **analysis
})

    except Exception as e:
        st.warning(f"⚠️ Skipping r/{sub_name}: {e}")
    return results

def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="posts")
    return buf.getvalue()

# ---------- Streamlit UI ----------
st.set_page_config(page_title="Reddit Fetch & Analytics", layout="wide")
st.title("📊 Reddit Fetch & Analytics (Upgraded)")
st.write("Fetch posts, inspect content, and view analytics. No background saving or scheduling included.")

# Sidebar: controls
with st.sidebar:
    st.header("Fetch Options")
    sub_input = st.text_input("Subreddits (comma separated)", "SaaS, startups, ProductManagement")
    subreddits = [s.strip() for s in sub_input.split(",") if s.strip()]
    kw_input = st.text_input("Keywords (comma separated, optional)", "SaaS, AI, automation")
    keywords = [k.strip() for k in kw_input.split(",") if k.strip()]
    date_col1, date_col2 = st.columns(2)
    with date_col1:
        start_date = st.date_input("Start date", value=None)
    with date_col2:
        end_date = st.date_input("End date", value=None)
    limit = st.slider("Posts per subreddit (limit)", 10, 500, 100)
    min_score = st.number_input("Min score (filter)", min_value=0, value=0, step=1)
    min_comments = st.number_input("Min comments (filter)", min_value=0, value=0, step=1)
    include_comments = st.checkbox("Show top comments preview", value=True)
    st.markdown("---")
    fetch_btn = st.button("🚀 Fetch Posts")

# Main: Tabs
tabs = st.tabs(["Posts", "Summary", "Analytics", "Settings"])
posts_df = pd.DataFrame()

if fetch_btn:
    all_posts = []
    progress_txt = st.empty()
    progress_bar = st.progress(0)
    total_subs = max(1, len(subreddits))
    for i, s in enumerate(subreddits, start=1):
        progress_txt.info(f"Fetching from r/{s} ({i}/{total_subs})")
        chunk = fetch_posts_from_subreddit(
            s, limit, keywords,
            None if start_date is None else start_date,
            None if end_date is None else end_date,
            int(min_score), int(min_comments)
        )
        all_posts.extend(chunk)
        progress_bar.progress(i/total_subs)
    progress_txt.success("Fetch complete.")
    progress_bar.empty()
    if all_posts:
        posts_df = pd.DataFrame(all_posts)
    else:
        st.warning("No posts matched your filters.")
else:
    st.info("Press 'Fetch Posts' in the sidebar to load data.")

# TAB — Posts
with tabs[0]:
    st.header("Posts")
    if not posts_df.empty:
        # Filters inside posts view
        col1, col2, col3 = st.columns([1,1,2])
        with col1:
            sub_filter = st.multiselect("Filter by subreddit", options=posts_df["Subreddit"].unique().tolist(), default=posts_df["Subreddit"].unique().tolist())
        with col2:
            author_filter = st.text_input("Author contains (optional)", "")
        with col3:
            title_search = st.text_input("Search in title/body (optional)", "")

        filtered = posts_df[posts_df["Subreddit"].isin(sub_filter)]
        if author_filter:
            filtered = filtered[filtered["Author"].str.contains(author_filter, case=False, na=False)]
        if title_search:
            mask = filtered["Title"].str.contains(title_search, case=False, na=False) | filtered["Body"].str.contains(title_search, case=False, na=False)
            filtered = filtered[mask]

        st.write(f"Showing {len(filtered)} posts")

        # render posts as collapsible cards
        for idx, row in filtered.iterrows():
            with st.expander(f"{row['Title'][:120]}"):
                cols = st.columns([8,2])
                with cols[0]:
                    st.markdown(f"**Subreddit:** `{row['Subreddit']}`  •  **Author:** {row['Author']}  •  **Score:** {row['Score']}  •  **Comments:** {row['CommentsCount']}")
                    body = row["Body"] or "(no text content)"
                    # highlight keywords
                    if keywords:
                        body_display = body
                        for kw in keywords:
                            if kw:
                                body_display = body_display.replace(kw, f"**{kw}**")
                        st.markdown(body_display)
                    else:
                        st.write(body)
                    if include_comments and row["TopComments"]:
                        st.markdown(f"**Top comments preview:** _{row['TopComments']}_")
                with cols[1]:
                    st.markdown(f"Created (UTC):  \n{row['Created_UTC']}")
                    st.markdown(f"[Open on Reddit]({row['URL']})")
        # download buttons (filtered)
        csv = filtered.to_csv(index=False).encode('utf-8')
        excel_bytes = df_to_excel_bytes(filtered)
        st.download_button("📥 Download CSV (filtered)", data=csv, file_name="reddit_posts_filtered.csv", mime="text/csv")
        st.download_button("💾 Download Excel (filtered)", data=excel_bytes, file_name="reddit_posts_filtered.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("No posts loaded yet. Use the sidebar to fetch.")

# TAB — Summary
with tabs[1]:
    st.header("Summary")
    if not posts_df.empty:
        summary = posts_df["Subreddit"].value_counts().reset_index()
        summary.columns = ["Subreddit", "count"]
        st.table(summary)
        total_posts = len(posts_df)
        st.metric("Total posts fetched", total_posts)
        top_score = posts_df.sort_values("Score", ascending=False).iloc[0]
        st.write("Top scoring post:")
        st.markdown(f"**{top_score['Title']}** — r/{top_score['Subreddit']} — score {top_score['Score']}")
    else:
        st.info("No data to summarize yet.")

# TAB — Analytics (charts)
with tabs[2]:
    st.header("Analytics")
    if not posts_df.empty:
        # Posts per subreddit (bar)
        count_df = posts_df["Subreddit"].value_counts().reset_index()
        count_df.columns = ["Subreddit", "Count"]
        bar = alt.Chart(count_df).mark_bar().encode(
            x=alt.X("Subreddit:N", sort='-y'),
            y="Count:Q",
            tooltip=["Subreddit", "Count"]
        ).properties(width=600, height=300, title="Posts per Subreddit")
        st.altair_chart(bar, use_container_width=True)

        # Posts over time
        posts_df["Created_dt"] = pd.to_datetime(posts_df["Created_UTC"])
        time_df = posts_df.set_index("Created_dt").resample("D").size().reset_index(name="count")
        line = alt.Chart(time_df).mark_line(point=True).encode(
            x="Created_dt:T",
            y="count:Q",
            tooltip=["Created_dt", "count"]
        ).properties(width=700, height=300, title="Posts over time (daily)")
        st.altair_chart(line, use_container_width=True)

        st.subheader("🔥 High Priority Insight Posts")

top_insights = posts_df.sort_values(
    "Insight_Priority", ascending=False
).head(10)

st.dataframe(
    top_insights[
        ["Subreddit", "Title", "Insight_Priority",
         "Pain_Flag", "Demand_Flag", "Cost_Flag"]
    ]
) 

        # Keyword frequency (simple)
        if keywords:
            kw_counts = {}
            for kw in keywords:
                kw_counts[kw] = posts_df.apply(lambda r: kw.lower() in (r["Title"] + " " + r["Body"]).lower(), axis=1).sum()
            kw_df = pd.DataFrame(list(kw_counts.items()), columns=["Keyword", "Count"])
            pie = alt.Chart(kw_df).mark_arc().encode(
                theta=alt.Theta("Count:Q"),
                color="Keyword:N",
                tooltip=["Keyword", "Count"]
            ).properties(width=400, height=300, title="Keyword frequency")
            st.altair_chart(pie, use_container_width=False)
    else:
        st.info("No data to plot yet. Fetch posts first.")

# TAB — Settings
with tabs[3]:
    st.header("Settings")
    st.write("No auto-save or scheduling configured.")
    st.markdown("""
    **Manual workflow:**  
    1. Use the sidebar controls and click **Fetch Posts**.  
    2. Inspect results in **Posts** tab.  
    3. Download CSV/Excel if you need to keep results.
    """)

st.markdown("---")
st.caption("Built with ❤️ — you can ask me to add authentication, deployment, or team sharing next.")






