"""Sarvam LLM integration: summarisation, classification and Q&A.

Works in two modes:
  * With SARVAM_API_KEY set  -> real LLM summaries + grounded Q&A.
  * Without a key           -> graceful "lite" mode: snippets and keyword
                               classification are used instead, and Q&A
                               explains how to enable it.

Get a free key at https://dashboard.sarvam.ai
"""

import json
import re

import requests

API_URL = "https://api.sarvam.ai/v1/chat/completions"
DEFAULT_MODEL = "sarvam-m"


def _extract_json(text):
    """Pull the first JSON array/object out of an LLM response."""
    text = text.strip()
    # strip markdown code fences if present
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    for opener, closer in (("[", "]"), ("{", "}")):
        start = text.find(opener)
        if start == -1:
            continue
        end = text.rfind(closer)
        if end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue
    return None


class SarvamLLM:
    def __init__(self, api_key="", model=DEFAULT_MODEL, timeout=60):
        self.api_key = (api_key or "").strip()
        self.model = model
        self.timeout = timeout

    @property
    def available(self):
        return bool(self.api_key)

    # ------------------------------------------------------------------ core
    def chat(self, messages, temperature=0.3):
        if not self.available:
            raise RuntimeError("SARVAM_API_KEY is not set")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        resp = requests.post(API_URL, headers=headers, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    # ------------------------------------------------------------- summaries
    def summarize_articles(self, articles):
        """Summarise a batch of articles.

        Returns {link: 2-3 line summary}. Empty dict if unavailable or on
        any failure — callers must fall back to the raw snippet.
        """
        if not self.available or not articles:
            return {}
        listing = []
        for i, a in enumerate(articles, start=1):
            snippet = (a.get("summary") or "")[:300]
            source = a.get("source") or "news"
            listing.append(f"{i}. [{source}] {a['title']}\n   snippet: {snippet}")
        prompt = (
            "You are a news editor. For each numbered news item below, write a "
            "crisp 2-3 sentence summary of what happened and why it matters. "
            "Base the summary ONLY on the title and snippet; do not invent facts. "
            "Reply with a JSON array only, no other text, in exactly this form:\n"
            '[{"index": 1, "summary": "..."}, ...]\n\n'
            "News items:\n" + "\n".join(listing)
        )
        try:
            raw = self.chat(
                [{"role": "user", "content": prompt}], temperature=0.2
            )
            parsed = _extract_json(raw)
            out = {}
            for entry in parsed if isinstance(parsed, list) else []:
                try:
                    idx = int(entry["index"]) - 1
                    summary = str(entry["summary"]).strip()
                    if 0 <= idx < len(articles) and summary:
                        out[articles[idx]["link"]] = summary
                except (KeyError, ValueError, TypeError):
                    continue
            return out
        except Exception:
            return {}

    # ---------------------------------------------------------- follow-up QA
    def answer_question(self, question, articles):
        """Answer a user question grounded ONLY in the given articles."""
        if not self.available:
            return (
                "Q&A needs a Sarvam API key. Copy .env.example to .env, add your "
                "key from https://dashboard.sarvam.ai and restart."
            )
        context_parts = []
        for i, a in enumerate(articles, start=1):
            context_parts.append(
                f"[{i}] {a['title']} ({a.get('source') or 'unknown source'})\n"
                f"{a.get('summary') or ''}"
            )
        prompt = (
            "Answer the user's question using ONLY the news items below. "
            "If they do not contain the answer, say so plainly. "
            "Cite items as [1], [2] where relevant.\n\n"
            "News items:\n" + "\n\n".join(context_parts)
            + f"\n\nUser question: {question}"
        )
        try:
            return self.chat(
                [{"role": "user", "content": prompt}], temperature=0.3
            )
        except Exception as exc:
            return f"(LLM call failed: {exc})"
