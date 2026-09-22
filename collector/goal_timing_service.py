"""Best-effort goal-timing enrichment for Stable V3.3.

Uses Firecrawl search + structured scrape against public pages, prioritising
SoccerSTATS and InPlayWise. Results are cached per date/match and never block
the core 10027s prediction pipeline.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from . import cache_manager
from .firecrawl_client import search_web, scrape_json

BINS = ("0-15", "16-30", "31-45", "46-60", "61-75", "76-90")
PRIORITY = ("soccerstats.com", "inplaywise.com")


def _cache_path(date: str, match: dict) -> Path:
    token = f"{date}|{match.get('match_id')}|{match.get('home_team')}|{match.get('away_team')}"
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
    path = cache_manager.CACHE_DIR / "goal_timing"
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{date}_{digest}.json"


def _urls(value):
    found = []
    def walk(node):
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        elif isinstance(node, str) and node.startswith(("http://", "https://")):
            found.append(node)
    walk(value)
    out = []
    seen = set()
    for url in found:
        if url not in seen:
            seen.add(url); out.append(url)
    return out


def _rank_url(url):
    host = urlparse(url).netloc.lower()
    for i, domain in enumerate(PRIORITY):
        if domain in host:
            return i
    return 99


def _shares(values):
    if not isinstance(values, list) or len(values) != 6:
        return None
    nums = []
    for x in values:
        try:
            nums.append(max(0.0, float(x)))
        except (TypeError, ValueError):
            return None
    total = sum(nums)
    if total <= 0:
        return None
    return [x / total for x in nums]


def _team(raw):
    if not isinstance(raw, dict):
        return None
    gf = _shares(raw.get("goals_for"))
    ga = _shares(raw.get("goals_against"))
    if not gf or not ga:
        return None
    return {
        "goals_for_share": gf,
        "goals_against_share": ga,
        "first_half_gf_share": sum(gf[:3]),
        "first_half_ga_share": sum(ga[:3]),
        "second_half_gf_share": sum(gf[3:]),
        "second_half_ga_share": sum(ga[3:]),
        "scope": raw.get("scope") or "unknown",
    }


def collect_goal_timing(date: str, match: dict) -> dict:
    path = _cache_path(date, match)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data["cache_hit"] = True
            return data
        except Exception:
            pass

    home = str(match.get("home_team") or "").strip()
    away = str(match.get("away_team") or "").strip()
    if not home or not away:
        return {"available": False, "reason": "missing_team_names"}

    query = f'"{home}" "{away}" 0-15 16-30 31-45 46-60 61-75 76-90 goals scored conceded'
    search = search_web(query, limit=5)
    candidates = sorted(_urls(search), key=_rank_url)
    if not candidates:
        return {"available": False, "reason": "no_public_timing_source"}

    schema = {
        "type": "object",
        "properties": {
            "home": {
                "type": "object",
                "properties": {
                    "team": {"type": "string"},
                    "goals_for": {"type": "array", "items": {"type": "number"}, "minItems": 6, "maxItems": 6},
                    "goals_against": {"type": "array", "items": {"type": "number"}, "minItems": 6, "maxItems": 6},
                    "scope": {"type": "string"}
                },
                "required": ["goals_for", "goals_against"]
            },
            "away": {
                "type": "object",
                "properties": {
                    "team": {"type": "string"},
                    "goals_for": {"type": "array", "items": {"type": "number"}, "minItems": 6, "maxItems": 6},
                    "goals_against": {"type": "array", "items": {"type": "number"}, "minItems": 6, "maxItems": 6},
                    "scope": {"type": "string"}
                },
                "required": ["goals_for", "goals_against"]
            }
        },
        "required": ["home", "away"]
    }
    prompt = (
        f"Extract pre-match goal scored/conceded timing distributions for {home} and {away}. "
        "Return exactly six bins in this order: 0-15,16-30,31-45,46-60,61-75,76-90. "
        "Numbers may be counts or percentages but must all use the same scale for one row. "
        "Use only statistics visible on the page; do not infer missing bins."
    )

    for url in candidates[:3]:
        try:
            raw = scrape_json(url, schema=schema, prompt=prompt)
            payload = raw.get("data", {}).get("json") if isinstance(raw, dict) else None
            h = _team((payload or {}).get("home"))
            a = _team((payload or {}).get("away"))
            if h and a:
                result = {
                    "available": True,
                    "source_url": url,
                    "source_domain": urlparse(url).netloc.lower(),
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "bins": list(BINS),
                    "home": h,
                    "away": a,
                    "cache_hit": False,
                }
                path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                return result
        except Exception:
            continue
    return {"available": False, "reason": "timing_extract_failed"}


def _needs_timing(match: dict) -> bool:
    """Spend timing lookups where HTFT uncertainty is most likely to matter."""
    if os.getenv("HH520_GOAL_TIMING_ONLY_UNCERTAIN", "1").strip() != "1":
        return True

    market = match.get("market") or {}
    try:
        q = [1 / float(market[k]) for k in ("home_odds", "draw_odds", "away_odds")]
        total = sum(q)
        p = [x / total for x in q]
        ordered = sorted(p, reverse=True)
        pmax = ordered[0]
        margin = ordered[0] - ordered[1]
    except Exception:
        return True

    page = match.get("page_probability") or {}
    try:
        page_vals = [float(page[k]) for k in ("home", "draw", "away")]
        page_pmax = max(page_vals)
    except Exception:
        page_pmax = None

    factors = match.get("research_factors") or {}
    structure = str(factors.get("structure") or "").strip()
    risk = str(factors.get("risk") or "").strip()
    pattern = str(factors.get("pattern") or "").strip()

    return (
        pmax < 0.73
        or margin < 0.12
        or (page_pmax is not None and page_pmax < 0.60)
        or structure == "均衡"
        or risk in {"中高", "高", "很高"}
        or "极端" in pattern
    )


def enrich_matches_with_goal_timing(date: str, matches: list[dict]) -> dict:
    if os.getenv("HH520_GOAL_TIMING_ENABLED", "0").strip() != "1":
        return {"enabled": False, "attempted": 0, "available": 0, "skipped_confirmed": 0}

    try:
        max_matches = int(os.getenv("HH520_GOAL_TIMING_MAX_MATCHES", "30"))
    except ValueError:
        max_matches = 30

    candidates = [m for m in matches if _needs_timing(m)]
    selected = candidates[:max(0, max_matches)]
    selected_ids = {id(m) for m in selected}
    attempted = available = 0

    for match in matches:
        if id(match) not in selected_ids:
            reason = "confirmed_skip" if match not in candidates else "daily_lookup_cap"
            match["goal_timing"] = {"available": False, "reason": reason}
            continue
        attempted += 1
        try:
            timing = collect_goal_timing(date, match)
        except Exception as exc:
            timing = {"available": False, "reason": f"collector_error:{type(exc).__name__}"}
        match["goal_timing"] = timing
        available += int(bool(timing.get("available")))

    return {
        "enabled": True,
        "attempted": attempted,
        "available": available,
        "skipped_confirmed": sum(1 for m in matches if (m.get("goal_timing") or {}).get("reason") == "confirmed_skip"),
        "lookup_capped": max(0, len(candidates) - len(selected)),
    }
