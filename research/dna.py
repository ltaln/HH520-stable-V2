"""League/Team DNA metrics for HH520 Research Lab.

Research-only descriptive aggregation. No output may alter Stable directly.
"""
from collections import defaultdict

METRICS = ("wdl", "score_exact", "score_top2", "htft", "htft_top2", "goals")


def _new_bucket():
    return {
        "matches": 0,
        "dates": set(),
        "metrics": {m: {"sample_count": 0, "hits": 0} for m in METRICS},
    }


def _finalize(bucket):
    return {
        "matches": bucket["matches"],
        "date_count": len(bucket["dates"]),
        "metrics": {
            metric: {
                "sample_count": stat["sample_count"],
                "hits": stat["hits"],
                "accuracy": (
                    stat["hits"] / stat["sample_count"]
                    if stat["sample_count"] else None
                ),
            }
            for metric, stat in bucket["metrics"].items()
        },
    }


def build_dna(error_report):
    league_buckets = defaultdict(_new_bucket)
    team_buckets = defaultdict(_new_bucket)

    for row in (error_report or {}).get("matches") or []:
        day = str(row.get("date") or "")
        league = str(row.get("league") or "UNKNOWN")
        teams = [
            str(row.get("home_team") or "").strip(),
            str(row.get("away_team") or "").strip(),
        ]

        lb = league_buckets[league]
        lb["matches"] += 1
        if day:
            lb["dates"].add(day)

        for team in teams:
            if not team:
                continue
            tb = team_buckets[team]
            tb["matches"] += 1
            if day:
                tb["dates"].add(day)

        for metric in METRICS:
            state = row.get(metric)
            if state not in {"HIT", "MISS"}:
                continue
            lb["metrics"][metric]["sample_count"] += 1
            lb["metrics"][metric]["hits"] += int(state == "HIT")
            for team in teams:
                if team:
                    team_buckets[team]["metrics"][metric]["sample_count"] += 1
                    team_buckets[team]["metrics"][metric]["hits"] += int(state == "HIT")

    league_dna = {
        league: _finalize(bucket)
        for league, bucket in sorted(league_buckets.items())
    }
    team_dna = [
        {"team": team, **_finalize(bucket)}
        for team, bucket in team_buckets.items()
    ]
    team_dna.sort(key=lambda x: (x["matches"], x["date_count"]), reverse=True)

    return {
        "league_dna": league_dna,
        "team_dna": team_dna,
        "stable_access": "FORBIDDEN",
        "status": "RESEARCH_ONLY",
    }
