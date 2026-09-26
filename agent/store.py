"""SQLite cache for fetched news articles."""

import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone

from .settings import DATA_DIR, DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id         TEXT PRIMARY KEY,
    genre      TEXT NOT NULL,
    title      TEXT NOT NULL,
    link       TEXT NOT NULL,
    source     TEXT,
    summary    TEXT,
    published  TEXT,
    fetched_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_articles_genre ON articles(genre);
"""


def _connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _connect() as conn:
        conn.executescript(SCHEMA)


def _aid(link):
    return hashlib.sha1((link or "").encode("utf-8")).hexdigest()


def save_articles(genre_id, articles):
    """Insert or refresh a batch of articles for one genre."""
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        for a in articles:
            conn.execute(
                """
                INSERT OR REPLACE INTO articles
                    (id, genre, title, link, source, summary, published, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _aid(a["link"]),
                    genre_id,
                    a["title"],
                    a["link"],
                    a.get("source", ""),
                    a.get("summary", ""),
                    a["published"].isoformat() if a.get("published") else now,
                    now,
                ),
            )


def update_summary(link, summary):
    with _connect() as conn:
        conn.execute(
            "UPDATE articles SET summary = ? WHERE id = ?",
            (summary, _aid(link)),
        )


def get_articles(genre_id, limit=10, max_age_hours=None):
    """Return cached articles for a genre, newest first."""
    query = "SELECT * FROM articles WHERE genre = ?"
    params = [genre_id]
    if max_age_hours:
        cutoff = (
            datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        ).isoformat()
        query += " AND published >= ?"
        params.append(cutoff)
    query += " ORDER BY published DESC LIMIT ?"
    params.append(limit)
    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def cache_valid(genre_id, minutes):
    """True if we fetched this genre recently enough to reuse the cache."""
    cutoff = (
        datetime.now(timezone.utc) - timedelta(minutes=minutes)
    ).isoformat()
    with _connect() as conn:
        row = conn.execute(
            "SELECT MAX(fetched_at) AS latest FROM articles WHERE genre = ?",
            (genre_id,),
        ).fetchone()
    if not row or not row["latest"]:
        return False
    return row["latest"] >= cutoff
