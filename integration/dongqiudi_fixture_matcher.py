"""Conservative fixture matching for HH520 10027S and Dongqiudi.

No network access or production integration. All kickoff values must be timezone-aware.
"""
from datetime import datetime, timezone
import re
import unicodedata


def normalize_name(value):
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", value)


def utc_kickoff(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("kickoff must include timezone")
    return value.astimezone(timezone.utc)


def canonical(value, aliases):
    key = normalize_name(value)
    mapping = {normalize_name(k): normalize_name(v) for k, v in aliases.items()}
    return mapping.get(key, key)


def match_fixture(base, candidates, league_aliases, team_aliases, tolerance_minutes=15):
    """Return (status, match). Never guess when candidates are ambiguous."""
    if tolerance_minutes < 0:
        raise ValueError("negative tolerance")
    matched = []
    base_time = utc_kickoff(base["kickoff"])
    base_league = canonical(base["league"], league_aliases)
    base_home = canonical(base["home"], team_aliases)
    base_away = canonical(base["away"], team_aliases)
    for item in candidates:
        try:
            same_league = canonical(item["league"], league_aliases) == base_league
            same_home = canonical(item["home"], team_aliases) == base_home
            same_away = canonical(item["away"], team_aliases) == base_away
            delta = abs((utc_kickoff(item["kickoff"]) - base_time).total_seconds())
        except (KeyError, ValueError, TypeError):
            continue
        if same_league and same_home and same_away and delta <= tolerance_minutes * 60:
            matched.append(item)
    if len(matched) == 1:
        return "MATCHED", matched[0]
    if len(matched) > 1:
        return "AMBIGUOUS_MATCH", None
    return "NO_FIXTURE_MATCH", None
