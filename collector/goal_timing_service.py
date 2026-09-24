"""Best-effort goal-timing enrichment for Stable V3.3.

Discovery is matchup-first so Chinese HH520 team names can resolve to public
match pages. Exact six-bin timing is preferred. When unavailable, a clearly
labelled first-half/second-half aggregate fallback may be used for HTFT
reweighting. Enrichment never blocks the 10027s prediction pipeline.
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
PRIORITY = ("soccerstats.com", "footystats.org", "inplaywise.com", "sofascore.com", "365scores.com")

TEAM_SEARCH_ALIASES = {
    "日本": "Japan", "乌拉圭": "Uruguay", "韩国": "South Korea", "厄瓜多尔": "Ecuador",
    "科索沃": "Kosovo", "爱尔兰": "Republic of Ireland", "葡萄牙": "Portugal", "威尔士": "Wales",
    "荷兰": "Netherlands", "德国": "Germany", "塞尔维亚": "Serbia", "希腊": "Greece",
    "挪威": "Norway", "丹麦": "Denmark",
}


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
            seen.add(url)
            out.append(url)
    return out


def _rank_url(url):
    host = urlparse(url).netloc.lower()
    for i, domain in enumerate(PRIORITY):
        if domain in host:
            return i
    return 99


def _supported_url(url):
    host = urlparse(url).netloc.lower()
    return any(domain in host for domain in PRIORITY)


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


def _rate(value):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    if x > 1.0:
        x /= 100.0
    if not 0.0 <= x <= 1.0:
        return None
    return x


def _team(raw):
    if not isinstance(raw, dict):
        return None
    gf = _shares(raw.get("goals_for"))
    ga = _shares(raw.get("goals_against"))
    if not gf or not ga:
        return None
    first_gf = sum(gf[:3])
    first_ga = sum(ga[:3])
    return {
        "goals_for_share": gf,
        "goals_against_share": ga,
        "first_half_gf_share": first_gf,
        "first_half_ga_share": first_ga,
        "second_half_gf_share": sum(gf[3:]),
        "second_half_ga_share": sum(ga[3:]),
        "first_half_gf_signal": first_gf,
        "first_half_ga_signal": first_ga,
        "scope": raw.get("scope") or "unknown",
    }


def _team_half_rates(raw):
    if not isinstance(raw, dict):
        return None
    fh_gf = _rate(raw.get("first_half_scoring_rate"))
    fh_ga = _rate(raw.get("first_half_conceding_rate"))
    sh_gf = _rate(raw.get("second_half_scoring_rate"))
    sh_ga = _rate(raw.get("second_half_conceding_rate"))
    if None in (fh_gf, fh_ga):
        return None
    return {
        "first_half_gf_signal": fh_gf,
        "first_half_ga_signal": fh_ga,
        "second_half_gf_signal": sh_gf,
        "second_half_ga_signal": sh_ga,
        "scope": raw.get("scope") or "unknown",
    }


def _schemas():
    six_bin = {
        "type": "object",
        "properties": {
            side: {
                "type": "object",
                "properties": {
                    "team": {"type": "string"},
                    "goals_for": {"type": "array", "items": {"type": "number"}, "minItems": 6, "maxItems": 6},
                    "goals_against": {"type": "array", "items": {"type": "number"}, "minItems": 6, "maxItems": 6},
                    "scope": {"type": "string"},
                },
                "required": ["goals_for", "goals_against"],
            }
            for side in ("home", "away")
        },
        "required": ["home", "away"],
    }
    half = {
        "type": "object",
        "properties": {
            side: {
                "type": "object",
                "properties": {
                    "team": {"type": "string"},
                    "first_half_scoring_rate": {"type": "number"},
                    "first_half_conceding_rate": {"type": "number"},
                    "second_half_scoring_rate": {"type": "number"},
                    "second_half_conceding_rate": {"type": "number"},
                    "scope": {"type": "string"},
                },
                "required": ["first_half_scoring_rate", "first_half_conceding_rate"],
            }
            for side in ("home", "away")
        },
        "required": ["home", "away"],
    }
    return six_bin, half


def _search_name(team):
    return TEAM_SEARCH_ALIASES.get(str(team).strip(), str(team).strip())


def _discover(home, away):
    home_q, away_q = _search_name(home), _search_name(away)
    queries = [
        f'{home_q} {away_q} FootyStats SoccerSTATS goal timing',
        f'{home_q} {away_q} football goal timing statistics',
        f'{home_q} vs {away_q} sofascore 365scores',
    ]
    urls = []
    for index, query in enumerate(queries):
        try:
            search = search_web(query, limit=8)
        except Exception:
            continue
        urls.extend(_urls(search))
        supported = [u for u in urls if _supported_url(u)]
        if supported:
            break
        if index == 0:
            continue
    unique = []
    seen = set()
    for url in sorted(urls, key=_rank_url):
        if url in seen or not _supported_url(url):
            continue
        seen.add(url)
        unique.append(url)
    return unique


def _discover_team(team):
    name = _search_name(team)
    queries = [
        f'{name} FootyStats goal timing scored conceded',
        f'{name} SoccerSTATS goal times',
        f'{name} football first half second half scoring statistics',
    ]
    urls = []
    for query in queries:
        try:
            urls.extend(_urls(search_web(query, limit=8)))
        except Exception:
            continue
    unique, seen = [], set()
    for url in sorted(urls, key=_rank_url):
        if url in seen or not _supported_url(url):
            continue
        seen.add(url)
        unique.append(url)
    return unique


def _single_team_schemas():
    six = {
        "type": "object",
        "properties": {
            "team": {"type": "string"},
            "goals_for": {"type": "array", "items": {"type": "number"}, "minItems": 6, "maxItems": 6},
            "goals_against": {"type": "array", "items": {"type": "number"}, "minItems": 6, "maxItems": 6},
            "scope": {"type": "string"},
        },
        "required": ["goals_for", "goals_against"],
    }
    half = {
        "type": "object",
        "properties": {
            "team": {"type": "string"},
            "first_half_scoring_rate": {"type": "number"},
            "first_half_conceding_rate": {"type": "number"},
            "second_half_scoring_rate": {"type": "number"},
            "second_half_conceding_rate": {"type": "number"},
            "scope": {"type": "string"},
        },
        "required": ["first_half_scoring_rate", "first_half_conceding_rate"],
    }
    return six, half


def _extract_single_team(team, urls):
    six_schema, half_schema = _single_team_schemas()
    errors = []
    for url in urls[:5]:
        try:
            raw = scrape_json(
                url,
                schema=six_schema,
                prompt=(
                    f'Extract PRE-MATCH goal timing statistics for {team}. '
                    'Return scored and conceded values for exactly six bins: '
                    '0-15,16-30,31-45,46-60,61-75,76-90. Do not invent missing data.'
                ),
            )
            payload = raw.get("data", {}).get("json") if isinstance(raw, dict) else None
            parsed = _team(payload or {})
            if parsed:
                return parsed, "six_bin", url, errors
        except Exception as exc:
            errors.append(f'six_bin:{urlparse(url).netloc}:{type(exc).__name__}')
        try:
            raw = scrape_json(
                url,
                schema=half_schema,
                prompt=(
                    f'Extract PRE-MATCH first-half and second-half scoring/conceding rates for {team}. '
                    'Return only rates visible on the page; do not infer unrelated statistics.'
                ),
            )
            payload = raw.get("data", {}).get("json") if isinstance(raw, dict) else None
            parsed = _team_half_rates(payload or {})
            if parsed:
                return parsed, "half_aggregate_fallback", url, errors
        except Exception as exc:
            errors.append(f'half:{urlparse(url).netloc}:{type(exc).__name__}')
    return None, None, None, errors


def _save(path, result):
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def collect_goal_timing(date: str, match: dict) -> dict:
    path = _cache_path(date, match)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            retry_failures = os.getenv("HH520_GOAL_TIMING_RETRY_FAILURES", "0").strip() == "1"
            if data.get("available") or not retry_failures:
                data["cache_hit"] = True
                return data
        except Exception:
            pass

    home = str(match.get("home_team") or "").strip()
    away = str(match.get("away_team") or "").strip()
    if not home or not away:
        return {"available": False, "reason": "missing_team_names"}

    candidates = _discover(home, away)
    if not candidates:
        return _save(path, {
            "available": False,
            "reason": "no_public_timing_source",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "cache_hit": False,
        })

    six_schema, half_schema = _schemas()
    six_prompt = (
        f"Extract PRE-MATCH goal scored/conceded timing distributions for {home} and {away}. "
        "Return exactly six bins in this order: 0-15,16-30,31-45,46-60,61-75,76-90. "
        "Numbers may be counts or percentages but must use one scale per row. "
        "Use only statistics visible on the page and do not invent missing bins."
    )
    half_prompt = (
        f"Extract PRE-MATCH first-half and second-half scoring/conceding rates for {home} and {away}. "
        "Return rates as percentages or fractions. If the page shows first-half clean-sheet rate "
        "instead of conceding rate, first_half_conceding_rate may be the exact complement. "
        "Do not infer from unrelated full-time statistics."
    )

    errors = []
    for url in candidates[:5]:
        try:
            raw = scrape_json(url, schema=six_schema, prompt=six_prompt)
            payload = raw.get("data", {}).get("json") if isinstance(raw, dict) else None
            h = _team((payload or {}).get("home"))
            a = _team((payload or {}).get("away"))
            if h and a:
                return _save(path, {
                    "available": True,
                    "timing_mode": "six_bin",
                    "source_url": url,
                    "source_domain": urlparse(url).netloc.lower(),
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "bins": list(BINS),
                    "home": h,
                    "away": a,
                    "cache_hit": False,
                })
        except Exception as exc:
            errors.append(f"six_bin:{urlparse(url).netloc}:{type(exc).__name__}")

        try:
            raw = scrape_json(url, schema=half_schema, prompt=half_prompt)
            payload = raw.get("data", {}).get("json") if isinstance(raw, dict) else None
            h = _team_half_rates((payload or {}).get("home"))
            a = _team_half_rates((payload or {}).get("away"))
            if h and a:
                return _save(path, {
                    "available": True,
                    "timing_mode": "half_aggregate_fallback",
                    "source_url": url,
                    "source_domain": urlparse(url).netloc.lower(),
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "bins": None,
                    "home": h,
                    "away": a,
                    "cache_hit": False,
                })
        except Exception as exc:
            errors.append(f"half:{urlparse(url).netloc}:{type(exc).__name__}")

    # Match pages often do not contain both teams' timing tables. Fall back to
    # independent team-stat pages and join them only after both sides succeed.
    home_urls = _discover_team(home)
    away_urls = _discover_team(away)
    h, h_mode, h_url, h_errors = _extract_single_team(_search_name(home), home_urls)
    a, a_mode, a_url, a_errors = _extract_single_team(_search_name(away), away_urls)
    errors.extend(h_errors)
    errors.extend(a_errors)
    if h and a:
        mode = h_mode if h_mode == a_mode else "mixed_team_sources"
        return _save(path, {
            "available": True,
            "timing_mode": mode,
            "source_url": [h_url, a_url],
            "source_domain": ",".join(sorted({urlparse(h_url).netloc.lower(), urlparse(a_url).netloc.lower()})),
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "bins": list(BINS) if mode == "six_bin" else None,
            "home": h,
            "away": a,
            "cache_hit": False,
            "discovery_mode": "independent_team_pages",
        })

    return _save(path, {
        "available": False,
        "reason": "timing_extract_failed",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "candidate_count": len(candidates),
        "home_candidate_count": len(home_urls),
        "away_candidate_count": len(away_urls),
        "errors": errors[-12:],
        "cache_hit": False,
    })


def _needs_timing(match: dict) -> bool:
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
    attempted = available = six_bin = half_fallback = 0

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
        if timing.get("available"):
            available += 1
            six_bin += int(timing.get("timing_mode") == "six_bin")
            half_fallback += int(timing.get("timing_mode") == "half_aggregate_fallback")

    return {
        "enabled": True,
        "attempted": attempted,
        "available": available,
        "six_bin": six_bin,
        "half_aggregate_fallback": half_fallback,
        "skipped_confirmed": sum(1 for m in matches if (m.get("goal_timing") or {}).get("reason") == "confirmed_skip"),
        "lookup_capped": max(0, len(candidates) - len(selected)),
    }
