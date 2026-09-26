# 📰 News Agent — sarvam-build

An AI news agent that fetches the latest news from the web (RSS + Google News),
deduplicates and ranks it, summarises each story with an LLM, lets the user pick
a **genre**, and answers follow-up questions grounded in the fetched articles.

Built as part of the sarvam-build project. Works out of the box with **no API
key** (lite mode: headlines + snippets), and unlocks AI summaries + Q&A when a
[Sarvam API key](https://dashboard.sarvam.ai) is configured.

## Features

- **Genre menu** — India, World, Politics, Business, Technology, Sports,
  Entertainment, Science, Health (fully configurable in `config.yaml`).
- **Live fetching** via Google News RSS plus optional direct publisher feeds
  (The Hindu etc.), no paid news API needed.
- **Dedupe & ranking** — syndicated copies of the same story are collapsed;
  newest articles surface first.
- **AI summaries** — each story gets a crisp 2–3 line summary from the
  Sarvam chat LLM (`sarvam-m`).
- **Grounded Q&A** — ask questions about the current stories; the model may
  only answer from the fetched articles.
- **SQLite cache** — genres are refetched only when the cache is older than
  `cache_minutes`, so restarts are instant.
- **Two interfaces** — an interactive CLI and a Streamlit web app.

## Project structure

```
sarvam-build/
├── agent/
│   ├── settings.py     # config + .env loading
│   ├── fetcher.py      # RSS / Google News fetching
│   ├── store.py        # SQLite cache
│   ├── processor.py    # dedupe, ranking, keyword classification fallback
│   └── summarizer.py   # Sarvam LLM: summaries + grounded Q&A
├── cli.py              # interactive terminal UI
├── app.py              # Streamlit web UI
├── config.yaml         # genres, feeds, cache settings
├── .env.example        # template for your API key
└── requirements.txt
```

## Setup

```bash
git clone https://github.com/aarya369/sarvam-build.git
cd sarvam-build
pip install -r requirements.txt

# optional, for AI summaries + Q&A:
cp .env.example .env     # then edit .env and paste your key
```

## Usage

**CLI:**

```bash
python cli.py
```

```
  Which genre interests you today?
   1) India
   2) World
   3) Politics
   ...
  agent> 3

  Top Politics news
  ------------------------------------------------------------
   1. <headline>
      (Reuters, 2h ago)

news> read 1        # full summary + link
news> ask what is the new bill about?   # LLM answers from these stories
news> back          # genre menu
```

**Web app:**

```bash
streamlit run app.py
```

Pick a genre in the sidebar, browse the summarised stories, and ask follow-up
questions in the chat box at the bottom.

## Configuration

Everything user-facing lives in `config.yaml`:

```yaml
genres:
  - id: business
    name: Business
    query: "India business economy news"   # Google News search query
    feeds:                                 # optional direct RSS feeds
      - "https://www.thehindu.com/business/Economy/rss/"
```

- Add a genre by adding an entry (any `id`, `name`, `query`).
- `settings.max_articles_per_genre` — stories shown per genre.
- `settings.cache_minutes` — how long a genre's cache is reused.

## How it works

```
Google News RSS + publisher feeds
        │
        ▼
   fetcher.py ──► processor.py (dedupe + rank)
        │
        ▼
    store.py (SQLite cache)
        │
        ▼
 summarizer.py (Sarvam chat LLM) ──► summaries + genre Q&A
        │
        ▼
   cli.py / app.py (genre menu → headlines → read / ask)
```

Without an API key the agent degrades gracefully: snippets from the feeds are
shown instead of LLM summaries, and Q&A is disabled.

## Roadmap ideas

- Daily digest via a scheduler (cron / GitHub Actions) instead of on-demand fetch.
- Multilingual digests — translate summaries into Hindi/Tamil with Sarvam
  Translate and read them aloud with TTS.
- Voice interface on top of the Q&A flow.
