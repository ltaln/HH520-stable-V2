"""Research-only dataset for HH520 V3.5 FT calibration.

Builds pre-match H/D/A feature rows with isolated result labels. It never
changes Stable and never uses post-match fields as model inputs.
"""
from copy import deepcopy

from engine.probability_layer import probability_layer

POSTMATCH_KEYS = {
    "result", "half_score", "full_score", "actual_score", "actual_half_score",
    "actual_outcome", "actual_total_goals", "result_label", "label_status",
    "label_match_method",
}


def _norm_match_id(value):
    raw = str(value or "").strip()
    digits = "".join(ch for ch in raw if ch.isdigit())
    return str(int(digits)) if digits else raw


def _key(item):
    return (str(item.get("date") or "")[:10], _norm_match_id(item.get("match_id")))


def build_v35_ft_dataset(records, labels):
    label_map = {_key(x): x for x in labels if isinstance(x, dict)}
    rows = []
    actual_counts = {"HOME": 0, "DRAW": 0, "AWAY": 0}
    valid = 0

    for record in records:
        if not isinstance(record, dict):
            continue
        label = label_map.get(_key(record))
        if not label:
            continue

        prematch = deepcopy(record)
        for key in POSTMATCH_KEYS:
            prematch.pop(key, None)

        probability = probability_layer(prematch)
        if not probability.get("valid"):
            continue

        actual = str(label.get("actual_outcome") or "").upper()
        if actual not in actual_counts:
            continue
        actual_counts[actual] += 1
        valid += 1

        probs = probability.get("probabilities") or {}
        market = probability.get("market_probabilities") or {}
        ordered = sorted(probs.items(), key=lambda kv: float(kv[1]), reverse=True)
        p1 = float(ordered[0][1]) if ordered else None
        p2 = float(ordered[1][1]) if len(ordered) > 1 else None

        rows.append({
            "date": str(record.get("date") or "")[:10],
            "match_id": record.get("match_id"),
            "league": record.get("league"),
            "home_team": record.get("home_team"),
            "away_team": record.get("away_team"),
            "actual_outcome": actual,
            "probabilities": {
                "home": probs.get("home"),
                "draw": probs.get("draw"),
                "away": probs.get("away"),
            },
            "market_probabilities": {
                "home": market.get("home"),
                "draw": market.get("draw"),
                "away": market.get("away"),
            },
            "current_direction": probability.get("direction"),
            "pmax": p1,
            "margin": None if p1 is None or p2 is None else p1 - p2,
            "draw_anchor": probability.get("draw_anchor"),
            "home_share": probability.get("home_share"),
        })

    return {
        "version": "HH520 V3.5 FT Calibration Dataset V1",
        "isolation": "RESEARCH_ONLY",
        "postmatch_fields_removed_before_probability": True,
        "valid_rows": valid,
        "actual_counts": actual_counts,
        "rows": rows,
    }
