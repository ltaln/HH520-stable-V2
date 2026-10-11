"""Dongqiudi pre-match collection adapter (candidate, not production-wired).

Fetches public HTML, extracts structured fixture and team stats when present.
Missing fields stay missing. Does not invent metrics or bypass site restrictions.
"""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse
import json
import re
import requests
from bs4 import BeautifulSoup

ALLOWED_HOSTS = {"dongqiudi.com", "www.dongqiudi.com", "m.dongqiudi.com"}
FIELDS = ("shots", "shots_on_target", "goals_for", "goals_against",
          "recent_form", "home_away_form", "goal_timing", "half_timing")
LABELS = {
    "shots": ("射门", "射门次数"),
    "shots_on_target": ("射正", "射正次数"),
    "goals_for": ("进球", "进球数"),
    "goals_against": ("失球", "丢球"),
}

def validate_url(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError("Only HTTPS Dongqiudi URLs are allowed")
    if parsed.username or parsed.password or parsed.port:
        raise ValueError("Invalid Dongqiudi URL")
    return url

def fetch_page(url, *, timeout=12, session=None):
    validate_url(url)
    client = session or requests.Session()
    response = client.get(url, timeout=timeout, headers={
        "User-Agent": "HH520-research/1.0 (public-page collector)"
    }, allow_redirects=False)
    response.raise_for_status()
    if 300 <= response.status_code < 400:
        raise ValueError("Redirect refused")
    if len(response.content) > 2_000_000:
        raise ValueError("Page too large")
    return response.text

def _numbers(value):
    return [float(v) for v in re.findall(r"(?<!\d)\d+(?:\.\d+)?(?!\d)", value)]

def parse_page(html, *, url, captured_at=None):
    """Extract only explicitly labeled stats; no post-match result inference."""
    validate_url(url)
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style", "noscript"]):
        node.decompose()
    text = soup.get_text(" ", strip=True)
    metrics = {}
    for field, labels in LABELS.items():
        for label in labels:
            # Require a label and exactly two immediately adjacent numeric values.
            pattern = rf"(?:^|\s){re.escape(label)}\s*[:：]?\s*(\d+(?:\.\d+)?)\s*[-:：/|]\s*(\d+(?:\.\d+)?)(?=\s|$)"
            match = re.search(pattern, text)
            if match:
                metrics[field] = {"home": float(match.group(1)),
                                  "away": float(match.group(2))}
                break
    now = captured_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("captured_at must be timezone-aware")
    return {
        "source": "dongqiudi",
        "source_url": url,
        "captured_at": now.astimezone(timezone.utc).isoformat(),
        "metrics": metrics,
        "missing_fields": [f for f in FIELDS if f not in metrics],
        "complete": False,
        "status": "PARTIAL" if metrics else "NO_STRUCTURED_STATS",
    }

def collect(url, *, as_of, session=None):
    """Fail closed if capture is not provably before match kickoff."""
    kickoff = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
    if kickoff.tzinfo is None:
        raise ValueError("as_of must include timezone")
    captured = datetime.now(timezone.utc)
    if captured >= kickoff:
        return {"status": "POST_KICKOFF_DATA", "source_url": validate_url(url),
                "metrics": {}, "complete": False}
    try:
        html = fetch_page(url, session=session)
        return parse_page(html, url=url, captured_at=captured)
    except (requests.RequestException, ValueError) as exc:
        return {"status": "SOURCE_UNAVAILABLE", "source_url": validate_url(url),
                "error": type(exc).__name__, "metrics": {}, "complete": False}
