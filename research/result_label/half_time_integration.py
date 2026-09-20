"""Research-only half-time/full-time evaluation helper."""
import re

from research.result_label.half_time_collector import build_htft


def _normalize_htft(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    upper = raw.upper().replace("-", "_").replace("/", "_").replace(" ", "")
    if re.fullmatch(r"(HOME|DRAW|AWAY)_(HOME|DRAW|AWAY)", upper):
        return upper

    token_map = {"主": "HOME", "胜": "HOME", "平": "DRAW", "客": "AWAY", "负": "AWAY"}
    chars = [c for c in raw if c in token_map]
    if len(chars) >= 2:
        return f"{token_map[chars[0]]}_{token_map[chars[1]]}"
    return None


def evaluate_half_time(predictions):
    total = 0
    hits = 0
    top2_hits = 0
    raw_total = 0
    derived_total = 0

    for item in predictions or []:
        label = item.get("result_label") or {}
        prediction = item.get("research_prediction") or {}
        page_prediction = prediction.get("page_prediction") or {}

        predicted_htft = (
            page_prediction.get("htft_normalized")
            or _normalize_htft(page_prediction.get("htft"))
        )
        half_score = label.get("actual_half_score") or label.get("half_score")
        full_score = label.get("actual_score") or label.get("full_score")

        if not predicted_htft or not half_score or not full_score:
            continue

        actual_htft = build_htft(half_score, full_score)
        if not actual_htft:
            continue

        total += 1
        hits += int(predicted_htft == actual_htft)

        top2 = page_prediction.get("htft_top2") or [predicted_htft]
        top2_norm = []
        for value in top2:
            norm = _normalize_htft(value)
            if norm and norm not in top2_norm:
                top2_norm.append(norm)
        top2_hits += int(actual_htft in top2_norm[:2])

        source = page_prediction.get("htft_source")
        if source == "RESEARCH_DERIVED_POISSON":
            derived_total += 1
        elif source == "HH520_RAW":
            raw_total += 1

    return {
        "status": "READY" if total else "RESEARCH_ONLY",
        "sample_count": total,
        "hits": hits,
        "accuracy": hits / total if total else None,
        "top2_hits": top2_hits,
        "top2_accuracy": top2_hits / total if total else None,
        "source_counts": {
            "hh520_raw": raw_total,
            "research_derived_poisson": derived_total,
        },
        "note": None if total else "No evaluable HT/FT predictions were available.",
    }
