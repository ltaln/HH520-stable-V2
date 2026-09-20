"""Research-only half-time integration helper.

Keeps half-time labels isolated from Stable. Used by Research reports only.
"""

from research.result_label.half_time_collector import build_htft


def evaluate_half_time(predictions):
    total = 0
    hits = 0

    for item in predictions or []:
        label = item.get("result_label") or {}
        prediction = item.get("research_prediction") or {}
        page_prediction = prediction.get("page_prediction") or {}

        predicted_htft = page_prediction.get("htft")
        half_score = label.get("half_score")
        full_score = label.get("full_score")

        if not predicted_htft or not half_score or not full_score:
            continue

        actual_htft = build_htft(half_score, full_score)
        if not actual_htft:
            continue

        total += 1
        hits += int(str(predicted_htft).upper() == str(actual_htft).upper())

    return {
        "status": "READY" if total else "RESEARCH_ONLY",
        "sample_count": total,
        "hits": hits,
        "accuracy": hits / total if total else None,
    }
