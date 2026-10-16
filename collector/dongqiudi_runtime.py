"""Production Dongqiudi enrichment for HH520 Stable V3.5.1.

This stage is additive: 10027S remains the base source. Dongqiudi is collected per
fixture and stored on the match as dongqiudi_enrichment. Missing/ambiguous
matches fail closed and never block the prediction pipeline.
"""
from __future__ import annotations

import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import cache_manager
from .dongqiudi_source import collect_match_analysis


def _cache_path(date: str, match: dict) -> Path:
    token = "|".join([
        str(date or ""),
        str(match.get("league") or ""),
        str(match.get("home_team") or ""),
        str(match.get("away_team") or ""),
        str(match.get("kickoff") or ""),
    ])
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:20]
    path = cache_manager.CACHE_DIR / "dongqiudi"
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{date}_{digest}.json"


def _load(path: Path):
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data["cache_hit"] = True
            return data
    except Exception:
        return None
    return None


def _save(path: Path, data: dict):
    data = dict(data)
    data.setdefault("cache_hit", False)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def collect_dongqiudi_for_match(date: str, match: dict) -> dict:
    path = _cache_path(date, match)
    cached = _load(path)
    retry_failures = os.getenv("HH520_DONGQIUDI_RETRY_FAILURES", "1").strip() == "1"
    if cached and (cached.get("available") or not retry_failures):
        return cached

    home = str(match.get("home_team") or "").strip()
    away = str(match.get("away_team") or "").strip()
    if not home or not away:
        return {"available": False, "reason": "missing_team_names", "cache_hit": False}

    try:
        result = collect_match_analysis(
            date, home, away,
            league=match.get("league"),
            kickoff=match.get("kickoff"),
        )
    except Exception as exc:
        result = {
            "available": False,
            "reason": f"dongqiudi_collector_error:{type(exc).__name__}",
        }

    result = dict(result or {})
    result["formal_enrichment"] = True
    result["fixture_identity"] = {
        "date": date,
        "league": match.get("league"),
        "kickoff": match.get("kickoff"),
        "home": home,
        "away": away,
    }
    return _save(path, result)


def enrich_matches_with_dongqiudi(date: str, matches: list[dict]) -> dict:
    if os.getenv("HH520_DONGQIUDI_ENABLED", "1").strip() != "1":
        for match in matches:
            match["dongqiudi_enrichment"] = {"available": False, "reason": "disabled"}
        return {"enabled": False, "attempted": 0, "available": 0, "cache_hits": 0}

    try:
        max_matches = max(0, int(os.getenv("HH520_DONGQIUDI_MAX_MATCHES", "100")))
    except ValueError:
        max_matches = 100
    selected = matches[:max_matches]

    try:
        workers = max(1, min(6, int(os.getenv("HH520_DONGQIUDI_WORKERS", "4"))))
    except ValueError:
        workers = 4

    future_map = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for match in selected:
            future_map[pool.submit(collect_dongqiudi_for_match, date, match)] = match
        for future in as_completed(future_map):
            match = future_map[future]
            try:
                result = future.result()
            except Exception as exc:
                result = {"available": False, "reason": f"runtime_error:{type(exc).__name__}"}
            match["dongqiudi_enrichment"] = result

    for match in matches[len(selected):]:
        match["dongqiudi_enrichment"] = {"available": False, "reason": "daily_lookup_cap"}

    return {
        "enabled": True,
        "attempted": len(selected),
        "available": sum(1 for m in selected if (m.get("dongqiudi_enrichment") or {}).get("available")),
        "cache_hits": sum(1 for m in selected if (m.get("dongqiudi_enrichment") or {}).get("cache_hit")),
        "lookup_capped": max(0, len(matches) - len(selected)),
        "formal_chain": True,
        "source": "DONGQIUDI_PUBLIC_ANALYSIS",
        "fixture_diagnostics": [
            {
                "home": str(m.get("home_team") or ""),
                "away": str(m.get("away_team") or ""),
                "league": m.get("league"),
                "kickoff": m.get("kickoff"),
                "available": bool((m.get("dongqiudi_enrichment") or {}).get("available")),
                "reason": (m.get("dongqiudi_enrichment") or {}).get("reason"),
                "match_detail_id": (m.get("dongqiudi_enrichment") or {}).get("match_detail_id"),
                "search_attempts": (m.get("dongqiudi_enrichment") or {}).get("search_attempts"),
                "candidate_count": (m.get("dongqiudi_enrichment") or {}).get("candidate_count"),
                "rejected_candidates": (m.get("dongqiudi_enrichment") or {}).get("rejected_candidates", []),
                "groups": (m.get("dongqiudi_enrichment") or {}).get("groups", {}),
            }
            for m in matches
        ],
    }
