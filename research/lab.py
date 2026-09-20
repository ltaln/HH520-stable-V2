"""HH520 Research Lab V2. Stable is read-only; outputs are candidate research only."""
from collections import Counter, defaultdict
from datetime import date, timedelta
from research.sanitizer import sanitize_records
from research.backtest_engine import evaluate

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
    return dict(leagues)


def _team_dna(records):
    teams = Counter()
    for r in records:
        for key in ("home_team", "away_team", "home", "away"):
            if r.get(key):
                teams[str(r[key])] += 1
    return [{"team": k, "sample_count": v} for k, v in teams.most_common()]


def _candidate_rules(records):
    return [{
        "id": "CR-SAMPLE-001",
        "status": "CANDIDATE_ONLY",
        "statement": "Sample supports segmented review only; no Stable change authorized.",
        "evidence_count": len(records),
    }] if len(records) >= 20 else []


def build_research_report(records, start=None, end=None, source="HH520_10023s", result_labels=None):
    clean, audit = sanitize_records(records)
    return {
        "system": "HH520 Research Lab V2",
        "stable_access": "READ_ONLY",
        "source": source,
        "window": {"from": start, "to": end},
        "input_count": len(records),
        "clean_count": len(clean),
        "sanitizer": {"pollution_events": len(audit), "audit": audit},
        "league_dna": _league_dna(clean),
        "team_dna": _team_dna(clean),
        "backtest": evaluate([] if result_labels is None else clean),
        "hidden_model_reverse": {"status": "RESEARCH_ONLY"},
        "risk_analysis": {"status": "RESEARCH_ONLY"},
        "causal_analysis": {"status": "HYPOTHESIS_ONLY"},
        "confidence_analysis": {"status": "RESEARCH_ONLY", "sample_count": len(clean)},
        "candidate_rules": _candidate_rules(clean),
        "promotion_policy": "MANUAL_REVIEW_REQUIRED",
    }
