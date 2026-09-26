"""RSS / Google News fetching."""

import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import requests

USER_AGENT = "Mozilla/5.0 (compatible; sarvam-build-news-agent/1.0)"

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"

ATOM_NS = "{http://www.w3.org/2005/Atom}"


def _strip_html(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_date(raw):
    """Best-effort parse of an RSS/Atom date string into an aware UTC datetime."""
    if not raw:
        return datetime.now(timezone.utc)
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _split_google_title(title):
    """Google News titles look like 'Headline - Source'. Split them apart."""
    if " - " in title:
        head, _, source = title.rpartition(" - ")
        if 2 <= len(source) <= 40:
            return head.strip(), source.strip()
    return title.strip(), ""


def _article(title, link, published, source, summary):
    return {
        "title": title,
        "link": (link or "").strip(),
        "published": published,
        "source": source,
        "summary": summary,
    }


def fetch_feed(url, timeout=15):
    """Fetch one RSS/Atom feed and return a list of article dicts."""
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    items = []
    # RSS 2.0
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = item.findtext("link") or ""
        if not link:
            link = (item.findtext("guid") or "").strip()
        source = (item.findtext("source") or "").strip()
        title, gsource = _split_google_title(title)
        source = source or gsource
        summary = _strip_html(item.findtext("description"))
        pub = _parse_date(item.findtext("pubDate"))
        if title and link:
            items.append(_article(title, link, pub, source, summary))

    # Atom fallback
    if not items:
        for entry in root.iter(ATOM_NS + "entry"):
            title = (entry.findtext(ATOM_NS + "title") or "").strip()
            link_el = entry.find(ATOM_NS + "link")
            link = link_el.get("href", "") if link_el is not None else ""
            source = ""
            summary = _strip_html(entry.findtext(ATOM_NS + "summary"))
            pub = _parse_date(entry.findtext(ATOM_NS + "updated"))
            if title and link:
                items.append(_article(title, link, pub, source, summary))

    return items


def genre_feed_urls(genre):
    """Build the list of feed URLs for a genre config entry."""
    urls = []
    query = genre.get("query")
    if query:
        urls.append(GOOGLE_NEWS_RSS.format(query=quote_plus(query)))
    urls.extend(genre.get("feeds") or [])
    return urls


def fetch_genre(genre, timeout=15):
    """Fetch and merge all feeds for one genre. Returns article dicts."""
    articles = []
    for url in genre_feed_urls(genre):
        try:
            articles.extend(fetch_feed(url, timeout=timeout))
        except Exception as exc:  # one bad feed should not kill the rest
            print(f"  [warn] could not fetch {url}: {exc}")
    return articles


def fetch_all(genres, timeout=15):
    """Fetch every genre. Returns {genre_id: [articles]}."""
    out = {}
    for genre in genres:
        gid = genre["id"]
        out[gid] = fetch_genre(genre, timeout=timeout)
    return out
