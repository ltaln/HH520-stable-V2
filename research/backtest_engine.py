"""Research-only backtest metrics. Never writes Stable parameters."""
import re

from research.result_label.half_time_integration import evaluate_half_time


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
            pair = (int(option["home"]), int(option["away"]))
            if pair not in parsed:
                parsed.append(pair)
        except (KeyError, TypeError, ValueError):
            pass

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


def _normalize_goal_prediction(raw):
    """Normalize common HH520 total-goals formats into a research rule."""
    text = str(raw or "").strip().replace(" ", "")
    if not text or text in {"-", "--", "—"}:
        return None

    # 3+, 3球以上, 3及以上, >=3
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:\+|球?以上|及以上)", text)
    if m:
        value = float(m.group(1))
        return {"type": "over_equal", "value": value}

    m = re.search(r"(?:大|over|>)\s*(\d+(?:\.\d+)?)", text, re.I)
    if m:
        line = float(m.group(1))
        return {"type": "over_line", "value": line}

    m = re.search(r"(?:小|under|<)\s*(\d+(?:\.\d+)?)", text, re.I)
    if m:
        line = float(m.group(1))
        return {"type": "under_line", "value": line}

    # 2-3, 2~3, 2～3, 2至3, 2到3
    m = re.search(r"(\d+)\s*(?:-|~|～|至|到)\s*(\d+)", text)
    if m:
        lo, hi = sorted((int(m.group(1)), int(m.group(2))))
        return {"type": "range", "min": lo, "max": hi}

    # Alternatives such as 2/3球, 2或3球, 2,3球, 2、3球.
    nums = [int(x) for x in re.findall(r"\d+", text)]
    if len(nums) >= 2 and any(token in text for token in ("/", "或", ",", "，", "、")):
        values = []
        for value in nums:
            if value not in values:
                values.append(value)
        return {"type": "set", "values": values}

    # Exact totals such as 3 or 3球.
    m = re.fullmatch(r"(\d+)球?", text)
    if m:
        return {"type": "exact", "value": int(m.group(1))}

    return None


def _goal_prediction_hit(item, actual_goals):
    if actual_goals is None:
        return None

    try:
        actual = int(actual_goals)
    except (TypeError, ValueError):
        return None

    _, prediction = _prediction_payload(item)
    rule = _normalize_goal_prediction(prediction.get("total_goals"))
    if rule is None:
        return None

    kind = rule["type"]
    if kind == "exact":
        return actual == rule["value"]
    if kind == "range":
        return rule["min"] <= actual <= rule["max"]
    if kind == "set":
        return actual in rule["values"]
    if kind == "over_equal":
        return actual >= rule["value"]
    if kind == "over_line":
        return actual > rule["value"]
    if kind == "under_line":
        return actual < rule["value"]
    return None


def evaluate(joined):
    matched = [
        x for x in joined
        if x.get("label_status") == "MATCHED" and x.get("result_label")
    ]

    wdl_total = wdl_hits = 0
    score_total = exact_hits = top2_hits = 0
    goals_total = goals_hits = 0

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


    half_time_metric = evaluate_half_time(matched)

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
            "half_time": half_time_metric,
            "goals": {
                "status": "READY" if goals_total else "RESEARCH_ONLY",
                "sample_count": goals_total,
                "hits": goals_hits,
                "accuracy": _ratio(goals_hits, goals_total),
            },
        },
        "note": "Result labels and prediction snapshots are isolated from Stable. No automatic promotion to Stable.",
    }
