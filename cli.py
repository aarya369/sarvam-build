#!/usr/bin/env python3
"""Interactive news agent CLI.

Usage:
    python cli.py

Inside the agent:
    <number>          open a genre
    read <n>          show the full summary + link for story n
    ask <question>    ask the LLM about the current stories
    refresh           refetch the current genre, ignoring the cache
    back              return to the genre menu
    quit              exit
"""

import sys
from datetime import datetime, timezone

from agent import fetcher, processor, store, summarizer
from agent.settings import get_api_key, load_config

BANNER = r"""
  _   _                 _
 | \ | | ___   ___ __ _| | ___  _ __ ___
 |  \| |/ _ \ / __/ _` | |/ _ \| '__/ __|
 | |\  | (_) | (_| (_| | | (_) | |  \__ \
 |_| \_|\___/ \___\__,_|_|\___/|_|  |___/
        ~ your AI news agent ~
"""

COMMANDS_HELP = (
    "commands: read <n> | ask <question> | refresh | back | quit"
)


def ago(dt_iso):
    """Human 'time ago' string from an ISO datetime string."""
    try:
        dt = datetime.fromisoformat(dt_iso)
    except (TypeError, ValueError):
        return ""
    delta = datetime.now(timezone.utc) - dt
    if dt.tzinfo is None:
        delta = datetime.utcnow().replace(tzinfo=timezone.utc) - dt
    minutes = int(delta.total_seconds() // 60)
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    return f"{hours // 24}d ago"


def load_genre_news(cfg, genre, use_cache=True):
    """Fetch (or reuse cached) articles for a genre, with LLM summaries."""
    gid = genre["id"]
    settings = cfg["settings"]
    limit = settings.get("max_articles_per_genre", 10)
    cache_minutes = settings.get("cache_minutes", 30)

    if use_cache and store.cache_valid(gid, cache_minutes):
        print("  (using cached articles)")
        return store.get_articles(gid, limit=limit)

    print(f"  fetching latest {genre['name']} news ...")
    raw = fetcher.fetch_genre(genre, timeout=settings.get("request_timeout", 15))
    articles = processor.process(raw, limit=limit)
    if not articles:
        return []
    store.save_articles(gid, articles)

    llm = summarizer.SarvamLLM(api_key=get_api_key())
    if llm.available:
        print("  summarising with the Sarvam LLM ...")
        summaries = llm.summarize_articles(articles)
        for link, text in summaries.items():
            store.update_summary(link, text)
        articles = store.get_articles(gid, limit=limit)
    return articles


def _print_article_list(articles):
    for i, a in enumerate(articles, start=1):
        meta_bits = [b for b in (a.get("source"), ago(a.get("published"))) if b]
        print(f"  {i:2d}. {a['title']}")
        if meta_bits:
            print(f"      ({', '.join(meta_bits)})")


def show_genre(cfg, genre):
    articles = load_genre_news(cfg, genre)
    if not articles:
        print("  No articles found. Try 'refresh' or another genre.")
        return

    print(f"\n  Top {genre['name']} news")
    print("  " + "-" * 60)
    _print_article_list(articles)

    while True:
        cmd = input("\nnews> ").strip()
        if not cmd:
            continue
        low = cmd.lower()
        if low in ("b", "back"):
            return
        if low in ("q", "quit", "exit"):
            sys.exit(0)
        if low in ("r", "refresh"):
            articles = load_genre_news(cfg, genre, use_cache=False)
            if not articles:
                print("  No articles found.")
                return
            print(f"\n  Refreshed {genre['name']} news")
            print("  " + "-" * 60)
            _print_article_list(articles)
            continue
        if low.startswith("read"):
            parts = cmd.split()
            if len(parts) == 2 and parts[1].isdigit() and 1 <= int(parts[1]) <= len(articles):
                a = articles[int(parts[1]) - 1]
                meta_bits = [
                    b for b in (a.get("source"), ago(a.get("published"))) if b
                ]
                print("\n  " + "=" * 60)
                print(f"  {a['title']}")
                if meta_bits:
                    print(f"  ({', '.join(meta_bits)})")
                print("  " + "=" * 60)
                print(a.get("summary") or "(no summary available)")
                print(f"\n  Full story: {a['link']}")
            else:
                print(f"  usage: read <1-{len(articles)}>")
            continue
        if low.startswith("ask"):
            question = cmd[3:].strip().lstrip("?").strip()
            if not question:
                print("  usage: ask <your question about these stories>")
                continue
            llm = summarizer.SarvamLLM(api_key=get_api_key())
            print("\n  thinking ...")
            print("\n" + llm.answer_question(question, articles))
            continue
        print(f"  unknown command. {COMMANDS_HELP}")


def main():
    cfg = load_config()
    genres = cfg["genres"]
    store.init_db()
    llm = summarizer.SarvamLLM(api_key=get_api_key())

    print(BANNER)
    if llm.available:
        print("  LLM: Sarvam connected (full summaries + Q&A enabled)")
    else:
        print("  LLM: not configured — running in lite mode (snippets only).")
        print("  Add SARVAM_API_KEY to .env to enable summaries and Q&A.")

    while True:
        print("\n  Which genre interests you today?")
        for i, g in enumerate(genres, start=1):
            print(f"  {i:2d}) {g['name']}")
        print("   q) quit")

        choice = input("\nagent> ").strip().lower()
        if choice in ("q", "quit", "exit"):
            print("\n  Bye! Stay informed.\n")
            return
        if choice.isdigit() and 1 <= int(choice) <= len(genres):
            show_genre(cfg, genres[int(choice) - 1])
        else:
            print("  pick a number from the list (or q to quit).")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\n\n  Bye! Stay informed.\n")
