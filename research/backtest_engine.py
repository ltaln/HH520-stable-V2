"""Research-only evaluation metrics. Never writes Stable parameters."""


def accuracy(total, hits):
    return hits / total if total else 0.0


def evaluate(joined):
    matched = [x for x in joined if x.get("label_status") == "MATCHED"]
    return {
        "sample_count": len(joined),
        "matched_results": len(matched),
        "metrics": {
            "win_draw_loss": {"status": "RESEARCH_ONLY"},
            "score": {"status": "RESEARCH_ONLY"},
            "half_time": {"status": "RESEARCH_ONLY"},
            "goals": {"status": "RESEARCH_ONLY"},
        },
        "note": "Metrics require matched result labels. No automatic promotion to Stable."
    }
