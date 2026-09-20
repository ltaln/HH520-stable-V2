"""HH520 Research Lab V1. Stable is read-only; outputs are candidate research only."""
from collections import Counter, defaultdict
from datetime import date, timedelta
from research.sanitizer import sanitize_records

MAX_DAYS = 31

def date_range(start, end):
    a, b = date.fromisoformat(start), date.fromisoformat(end)
    if b < a:
        raise ValueError("end date must be >= start date")
    days = (b - a).days + 1
    if days > MAX_DAYS:
        raise ValueError(f"research window must be <= {MAX_DAYS} days")
    return [(a + timedelta(days=i)).isoformat() for i in range(days)]

def _league_dna(records):
    leagues = defaultdict(lambda: {"matches": 0, "ready": 0})
    for r in records:
        league = str(r.get("league") or r.get("competition") or "UNKNOWN")
        leagues[league]["matches"] += 1
        if r.get("status") in ("READY_FOR_GPT", "LOCAL", "READY"):
            leagues[league]["ready"] += 1
    return dict(leagues)

def _team_dna(records):
    teams = Counter()
    for r in records:
        for key in ("home_team", "away_team", "home", "away"):
            if r.get(key):
                teams[str(r[key])] += 1
    return [{"team": team, "sample_count": count} for team, count in teams.most_common()]

def _candidate_rules(records):
    rules = []
    n = len(records)
    if n >= 20:
        rules.append({
            "id": "CR-SAMPLE-001",
            "status": "CANDIDATE_ONLY",
            "statement": "Sample size is sufficient for segmented review; no Stable change is authorized.",
            "evidence_count": n,
        })
    return rules

def build_research_report(records, start=None, end=None, source="HH520_10023s"):
    clean, audit = sanitize_records(records)
    status_counts = Counter(str(r.get("status", "UNKNOWN")) for r in clean)
    return {
        "system": "HH520 Research Lab V1",
        "stable_access": "READ_ONLY",
        "source": source,
        "window": {"from": start, "to": end},
        "input_count": len(records),
        "clean_count": len(clean),
        "sanitizer": {
            "pollution_events": len(audit),
            "audit": audit,
        },
        "status_counts": dict(status_counts),
        "league_dna": _league_dna(clean),
        "team_dna": _team_dna(clean),
        "hidden_model_reverse": {
            "status": "RESEARCH_ONLY",
            "note": "Produces observations only; never writes Stable parameters."
        },
        "risk_analysis": {
            "status": "RESEARCH_ONLY",
            "pass_or_unknown_count": sum(v for k, v in status_counts.items() if k in ("PASS", "UNKNOWN")),
        },
        "causal_analysis": {
            "status": "HYPOTHESIS_ONLY",
            "note": "Associations are not promoted to causal claims without controlled evidence."
        },
        "confidence_analysis": {
            "status": "RESEARCH_ONLY",
            "sample_count": len(clean),
        },
        "candidate_rules": _candidate_rules(clean),
        "promotion_policy": "MANUAL_REVIEW_REQUIRED",
    }
