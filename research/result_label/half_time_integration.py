"""Research-only half-time integration helper."""
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

    for item in predictions or []:
        label = item.get("result_label") or {}
        prediction = item.get("research_prediction") or {}
        page_prediction = prediction.get("page_prediction") or {}

        predicted_htft = _normalize_htft(page_prediction.get("htft"))
        half_score = label.get("half_score")
        full_score = label.get("full_score")

        if not predicted_htft or not half_score or not full_score:
            continue

        actual_htft = build_htft(half_score, full_score)
        if not actual_htft:
            continue

        total += 1
        hits += int(predicted_htft == actual_htft)

    return {
        "status": "READY" if total else "RESEARCH_ONLY",
        "sample_count": total,
        "hits": hits,
        "accuracy": hits / total if total else None,
        "note": None if total else "No verified external half-time labels matched HT/FT predictions.",
    }
