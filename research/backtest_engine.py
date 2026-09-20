"""Research-only backtest metrics. Never writes Stable parameters."""
import re


def _ratio(hits, total):
    return hits / total if total else None


def _actual_score(label):
    text = str(label.get("full_score") or "")
    m = re.fullmatch(r"\s*(\d+)\s*[-:：]\s*(\d+)\s*", text)
    return (int(m.group(1)), int(m.group(2))) if m else None


def _prediction_payload(item):
    research = item.get("research_prediction") or {}
    return (
        research.get("page_probability"),
        research.get("page_prediction") or {},
    )


def _parse_scores(prediction):
    """Parse ordered score choices from the raw 10023s prediction text."""
    options = prediction.get("score_options") or []
    parsed = []
    for option in options:
        try:
            parsed.append((int(option["home"]), int(option["away"])))
        except (KeyError, TypeError, ValueError):
            pass

    if parsed:
        return parsed

    raw = str(prediction.get("scores") or "")
    for home, away in re.findall(r"(\d+)\s*[-:：]\s*(\d+)", raw):
        pair = (int(home), int(away))
        if pair not in parsed:
            parsed.append(pair)
    return parsed


def _predicted_outcome(item):
    probs, prediction = _prediction_payload(item)
    probs = probs or {}

    if all(k in probs for k in ("home", "draw", "away")):
        return max(("home", "draw", "away"), key=lambda k: probs.get(k, -1)).upper()

    single = str(prediction.get("single") or "").strip()
    mapping = {
        "主": "HOME", "主胜": "HOME", "home": "HOME",
        "平": "DRAW", "平局": "DRAW", "draw": "DRAW",
        "客": "AWAY", "客胜": "AWAY", "away": "AWAY",
    }
    mapped = mapping.get(single.lower()) or mapping.get(single)
    if mapped:
        return mapped

    # Current 10023s parser may not expose fused probability/single.
    # Use the first predicted score as a Research-only direction fallback.
    scores = _parse_scores(prediction)
    if scores:
        home, away = scores[0]
        if home > away:
            return "HOME"
        if home < away:
            return "AWAY"
        return "DRAW"
    return None


def _score_options(item):
    _, prediction = _prediction_payload(item)
    return _parse_scores(prediction)


def _goal_prediction_hit(item, actual_goals):
    if actual_goals is None:
        return None
    _, prediction = _prediction_payload(item)
    raw = str(prediction.get("total_goals") or "").strip()
    if not raw:
        return None

    nums = [int(x) for x in re.findall(r"\d+", raw)]
    if not nums:
        return None

    if any(token in raw for token in ("+", "以上", "及以上")):
        return actual_goals >= nums[0]
    if any(token in raw for token in ("-", "~", "～", "至")) and len(nums) >= 2:
        lo, hi = min(nums[0], nums[1]), max(nums[0], nums[1])
        return lo <= actual_goals <= hi
    if len(nums) == 1:
        return actual_goals == nums[0]
    return None


def evaluate(joined):
    matched = [
        x for x in joined
        if x.get("label_status") == "MATCHED" and x.get("result_label")
    ]

    wdl_total = wdl_hits = 0
    score_total = exact_hits = top2_hits = 0
    goals_total = goals_hits = 0
    half_total = half_hits = 0

    for item in matched:
        label = item["result_label"]

        predicted = _predicted_outcome(item)
        actual = str(label.get("result") or "").upper()
        if predicted and actual in {"HOME", "DRAW", "AWAY"}:
            wdl_total += 1
            wdl_hits += int(predicted == actual)

        actual_score = _actual_score(label)
        options = _score_options(item)
        if actual_score and options:
            score_total += 1
            exact_hits += int(actual_score == options[0])
            top2_hits += int(actual_score in options[:2])

        goal_hit = _goal_prediction_hit(item, label.get("goals"))
        if goal_hit is not None:
            goals_total += 1
            goals_hits += int(goal_hit)

        _, prediction = _prediction_payload(item)
        # Keep HT/FT unavailable until an independent half-time result source exists.
        if label.get("half_score") and prediction.get("htft"):
            half_total += 1

    return {
        "status": "BACKTEST_READY" if matched else "RESEARCH_ONLY",
        "sample_count": len(joined),
        "matched_results": len(matched),
        "metrics": {
            "win_draw_loss": {
                "status": "READY" if wdl_total else "RESEARCH_ONLY",
                "sample_count": wdl_total,
                "hits": wdl_hits,
                "accuracy": _ratio(wdl_hits, wdl_total),
                "direction_source": "probability_or_single_or_primary_score",
            },
            "score": {
                "status": "READY" if score_total else "RESEARCH_ONLY",
                "sample_count": score_total,
                "exact_hits": exact_hits,
                "exact_accuracy": _ratio(exact_hits, score_total),
                "top2_hits": top2_hits,
                "top2_accuracy": _ratio(top2_hits, score_total),
            },
            "half_time": {
                "status": "READY" if half_total else "RESEARCH_ONLY",
                "sample_count": half_total,
                "hits": half_hits,
                "accuracy": _ratio(half_hits, half_total),
                "note": None if half_total else "No independent half-time result label available.",
            },
            "goals": {
                "status": "READY" if goals_total else "RESEARCH_ONLY",
                "sample_count": goals_total,
                "hits": goals_hits,
                "accuracy": _ratio(goals_hits, goals_total),
            },
        },
        "note": "Result labels and prediction snapshots are isolated from Stable. No automatic promotion to Stable.",
    }
