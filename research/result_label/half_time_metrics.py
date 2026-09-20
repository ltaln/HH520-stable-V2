"""Research-only half-time and HT/FT metrics."""


def ratio(hits, total):
    return hits / total if total else None


def evaluate_half_time_labels(labels, predicted_htft_key="htft"):
    total = 0
    hits = 0

    for item in labels:
        actual = item.get("htft")
        predicted = item.get(predicted_htft_key)
        if actual and predicted:
            total += 1
            hits += int(actual == predicted)

    return {
        "status": "READY" if total else "RESEARCH_ONLY",
        "sample_count": total,
        "hits": hits,
        "accuracy": ratio(hits, total),
    }
