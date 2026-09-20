"""Research-only external half-time result source.

Uses Firecrawl Search to look up historical half-time scores only for matches
that already have an HH520 HT/FT prediction. Results are cached to protect the
Firecrawl quota. A score is accepted only when a half-time marker and the
known full-time score are both present in the same search result text.
"""
import json
import re
from pathlib import Path

from collector.firecrawl_client import search_web

CACHE_DIR = Path("cache/research_half_time")

_HT_PATTERNS = [
    re.compile(r"(?:\bHT\b|H/T|half[ -]?time|halftime|半场(?:比分)?|上半场)\s*[:：\-]?\s*(\d+)\s*[-:：]\s*(\d+)", re.I),
    re.compile(r"(\d+)\s*[-:：]\s*(\d+)\s*(?:\(\s*HT\s*\)|\bHT\b)", re.I),
]


def _norm(value):
    return " ".join(str(value or "").strip().split())


def _safe_token(value):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", _norm(value))[:80]


def _cache_path(record):
    day = _safe_token(record.get("date"))
    match_id = _safe_token(record.get("match_id")) or "unknown"
    return CACHE_DIR / f"{day}-{match_id}.json"


def _search_items(payload):
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, dict):
        web = data.get("web")
        if isinstance(web, list):
            return web
    if isinstance(data, list):
        return data
    return []


def _text(item):
    if not isinstance(item, dict):
        return ""
    return "\n".join(str(item.get(k) or "") for k in ("title", "description", "markdown", "url"))


def _extract_half_score(text, full_score):
    raw = str(text or "")
    normalized_full = str(full_score or "").replace(":", "-").replace("：", "-").replace(" ", "")
    compact = raw.replace(":", "-").replace("：", "-").replace(" ", "")
    if normalized_full and normalized_full not in compact:
        return None
    for pattern in _HT_PATTERNS:
        match = pattern.search(raw)
        if match:
            return f"{int(match.group(1))}-{int(match.group(2))}"
    return None


def _has_htft_prediction(record):
    source = record.get("research_source_prediction") or {}
    prediction = source.get("page_prediction") or record.get("page_prediction") or {}
    value = str(prediction.get("htft") or "").strip()
    return bool(value and value not in {"-", "--", "—"})


def _label_key(item):
    return (str(item.get("date") or ""), str(item.get("match_id") or ""))


def enrich_half_time_labels(records, labels):
    """Return labels enriched with independently searched half-time scores."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    label_map = {_label_key(label): dict(label) for label in labels}
    searched = cache_hits = found = accepted = errors = 0

    for record in records:
        if not isinstance(record, dict) or not _has_htft_prediction(record):
            continue

        key = _label_key(record)
        label = label_map.get(key)
        if not label or label.get("half_score") or not label.get("full_score"):
            continue

        path = _cache_path(record)
        cached = None
        if path.exists():
            try:
                cached = json.loads(path.read_text(encoding="utf-8"))
                cache_hits += 1
            except Exception:
                cached = None

        if cached is None:
            query = (
                f'{record.get("date","")} "{record.get("home_team","")}" '
                f'"{record.get("away_team","")}" halftime score HT'
            )
            try:
                payload = search_web(query, limit=5)
                searched += 1
                cached = {"status": "NOT_FOUND", "half_score": None, "source_url": None}
                for item in _search_items(payload):
                    score = _extract_half_score(_text(item), label.get("full_score"))
                    if score:
                        cached = {
                            "status": "FOUND",
                            "half_score": score,
                            "source_url": item.get("url"),
                        }
                        found += 1
                        break
            except Exception as exc:
                errors += 1
                cached = {"status": "ERROR", "half_score": None, "error": str(exc)[:200]}

            path.write_text(json.dumps(cached, ensure_ascii=False, indent=2), encoding="utf-8")

        if cached.get("status") == "FOUND" and cached.get("half_score"):
            label["half_score"] = cached["half_score"]
            label["half_time_source"] = cached.get("source_url") or "FIRECRAWL_SEARCH"
            label["half_time_verified"] = True
            accepted += 1
            label_map[key] = label

    enriched = [label_map.get(_label_key(label), dict(label)) for label in labels]
    return enriched, {
        "enabled": True,
        "provider": "FIRECRAWL_SEARCH",
        "searched": searched,
        "cache_hits": cache_hits,
        "found": found,
        "accepted": accepted,
        "errors": errors,
        "isolation": "RESEARCH_ONLY",
        "stable_access": "FORBIDDEN",
    }
