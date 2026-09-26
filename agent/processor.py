"""Article processing: dedupe, rank, and keyword-based genre classification."""

import difflib
import re
from datetime import datetime, timezone

# Used only as a fallback when the Sarvam LLM key is not configured.
GENRE_KEYWORDS = {
    "politics": [
        "election", "minister", "parliament", "government", "party", "lok sabha",
        "rajya sabha", "assembly", "vote", "coalition", "prime minister", "chief minister",
        "congress", "bjp", "seat", "poll", "cabinet",
    ],
    "business": [
        "market", "stock", "rupee", "economy", "gdp", "inflation", "ipo",
        "revenue", "profit", "startup funding", "sensex", "nifty", "trade",
        "tariff", "bank", "investment", "rupees", "crore",
    ],
    "technology": [
        "ai", "artificial intelligence", "app", "software", "chip", "semiconductor",
        "smartphone", "internet", "startup", "openai", "google", "microsoft",
        "iphone", "android", "launch", "gadget", "cyber", "data",
    ],
    "sports": [
        "cricket", "match", "ipl", "tournament", "cup", "goal", "olympic",
        "badminton", "hockey", "football", "tennis", "chess", "world cup",
        "series", "wicket", "medal", "coach", "athlete",
    ],
    "entertainment": [
        "film", "movie", "bollywood", "actor", "actress", "song", "trailer",
        "netflix", "series", "box office", "ott", "celebrity", "drama",
        "concert", "album",
    ],
    "science": [
        "research", "scientists", "space", "isro", "nasa", "study finds",
        "physics", "climate", "species", "discovery", "experiment", "telescope",
        "mars", "satellite",
    ],
    "health": [
        "health", "hospital", "disease", "vaccine", "virus", "outbreak",
        "doctor", "medical", "fitness", "mental health", "diet", "cancer",
        "diabetes", "infection", "who warns",
    ],
    "world": [
        "united states", "china", "russia", "ukraine", "israel", "gaza",
        "united nations", "nato", "european", "pakistan", "war", "summit",
        "president", "global",
    ],
    "india": [
        "india", "delhi", "mumbai", "supreme court", "modi", "indian",
        "centre", "state government", "monsoon", "indian railways",
    ],
}


def normalize_title(title):
    return re.sub(r"[^a-z0-9 ]", "", (title or "").lower()).strip()


def dedupe(articles, threshold=0.75):
    """Drop near-duplicate stories (same story syndicated across outlets)."""
    kept, normalized = [], []
    for a in articles:
        nt = normalize_title(a["title"])
        if not nt:
            continue
        if any(
            difflib.SequenceMatcher(None, nt, k).ratio() >= threshold
            for k in normalized
        ):
            continue
        kept.append(a)
        normalized.append(nt)
    return kept


def rank(articles):
    """Newest first; articles without dates sink to the end."""
    now = datetime.now(timezone.utc)

    def sort_key(a):
        pub = a.get("published") or now
        return pub

    return sorted(articles, key=sort_key, reverse=True)


def process(articles, limit=10):
    """Dedupe -> rank -> trim to the number we display."""
    return rank(dedupe(articles))[:limit]


def classify_fallback(title, snippet=""):
    """Keyword-vote a headline into a genre id (used without an API key)."""
    text = f"{title} {snippet}".lower()
    best_genre, best_score = None, 0
    for genre, keywords in GENRE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_genre, best_score = genre, score
    return best_genre
