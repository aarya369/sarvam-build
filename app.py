#!/usr/bin/env python3
"""Streamlit web UI for the news agent.

Run with:
    streamlit run app.py
"""

from datetime import datetime, timezone

import streamlit as st

from agent import fetcher, processor, store, summarizer
from agent.settings import get_api_key, load_config

st.set_page_config(page_title="News Agent", page_icon="📰", layout="wide")


def ago(dt_iso):
    try:
        dt = datetime.fromisoformat(dt_iso)
    except (TypeError, ValueError):
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    minutes = int((datetime.now(timezone.utc) - dt).total_seconds() // 60)
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes} min ago"
    if minutes < 1440:
        return f"{minutes // 60} hr ago"
    return f"{minutes // 1440} d ago"


@st.cache_data(ttl=1800, show_spinner=False)
def load_genre_news(genre_dict, limit):
    """Fetch + process + cache (per genre, TTL 30 min)."""
    raw = fetcher.fetch_genre(genre_dict, timeout=15)
    return processor.process(raw, limit=limit)


cfg = load_config()
genres = cfg["genres"]
settings = cfg["settings"]
limit = settings.get("max_articles_per_genre", 10)

store.init_db()
llm = summarizer.SarvamLLM(api_key=get_api_key())

st.title("📰 News Agent")
st.caption("Latest news, fetched live and summarised by AI.")

with st.sidebar:
    st.header("Pick a genre")
    genre_names = [g["name"] for g in genres]
    genre = st.radio("genre", genre_names, label_visibility="collapsed")
    genre_dict = next(g for g in genres if g["name"] == genre)
    st.divider()
    if llm.available:
        st.success("Sarvam LLM connected — summaries and Q&A enabled.")
    else:
        st.warning(
            "Running in lite mode. Add SARVAM_API_KEY to .env for "
            "AI summaries and Q&A."
        )

if st.button("🔄 Refresh news", use_container_width=True):
    load_genre_news.clear()

with st.spinner(f"Fetching latest {genre} news..."):
    articles = load_genre_news(genre_dict, limit)

if not articles:
    st.info("No articles found for this genre. Try another one or refresh.")
    st.stop()

store.save_articles(genre_dict["id"], articles)

if llm.available:
    with st.spinner("Summarising with Sarvam LLM..."):
        summaries = llm.summarize_articles(articles)
    for a in articles:
        if a["link"] in summaries:
            a["summary"] = summaries[a["link"]]
        store.update_summary(a["link"], a.get("summary") or "")

st.subheader(f"Top {genre} news")

for i, a in enumerate(articles, start=1):
    meta_bits = [b for b in (a.get("source"), ago(a.get("published"))) if b]
    header = f"{i}. {a['title']}"
    with st.expander(header, expanded=(i <= 3)):
        if meta_bits:
            st.caption(" • ".join(meta_bits))
        st.write(a.get("summary") or "_(no summary available)_")
        st.markdown(f"[Read the full story]({a['link']})")

st.divider()
question = st.chat_input("Ask a question about these stories...")
if question:
    if llm.available:
        with st.spinner("Thinking..."):
            answer = llm.answer_question(question, articles)
    else:
        answer = (
            "Q&A needs a Sarvam API key. Copy .env.example to .env, add your "
            "key from https://dashboard.sarvam.ai and restart the app."
        )
    with st.chat_message("user"):
        st.write(question)
    with st.chat_message("assistant"):
        st.write(answer)
