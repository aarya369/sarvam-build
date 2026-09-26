"""Shared configuration and environment helpers."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "news.db"
ENV_PATH = PROJECT_ROOT / ".env"

_env_loaded = False


def load_env(path=None):
    """Minimal .env loader (KEY=VALUE lines). No python-dotenv needed."""
    global _env_loaded
    if _env_loaded:
        return
    _env_loaded = True
    path = Path(path or ENV_PATH)
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def load_config(path=None):
    """Load config.yaml and return it as a dict."""
    import yaml

    with open(path or CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_api_key():
    """Return the Sarvam API key from the environment or .env file."""
    load_env()
    return os.environ.get("SARVAM_API_KEY", "").strip()
