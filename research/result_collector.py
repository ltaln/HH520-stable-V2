"""Independent result label collector for HH520 Research Lab V2.

This module is intentionally separated from prematch collection.
It must never modify Stable input data.
"""


def normalize_result(match_id, payload):
    """Convert an external result payload into a research-only label."""
    return {
        "match_id": str(match_id),
        "final_score": payload.get("final_score") or payload.get("score"),
        "half_score": payload.get("half_score"),
        "result": payload.get("result"),
        "goals": payload.get("goals"),
        "source": payload.get("source", "UNKNOWN"),
    }


def collect_results(match_ids, provider=None):
    """Placeholder interface.

    A provider can later be attached without changing Research or Stable.
    Missing labels remain UNKNOWN.
    """
    labels = []
    for match_id in match_ids:
        if provider:
            data = provider(match_id)
            labels.append(normalize_result(match_id, data))
        else:
            labels.append({
                "match_id": str(match_id),
                "status": "UNKNOWN"
            })
    return labels
