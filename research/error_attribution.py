"""Per-match Research error attribution.

Creates explicit hit/miss labels for WDL, score, HT/FT and total goals without
changing predictions or Stable. Result labels and Research predictions remain
isolated.
"""
import re

from research.result_label.half_time_collector import build_htft


def _score_pair(value):
    m = re.search(r"(\d+)\s*[-:：]\s*(\d+)", str(value or ""))
    return (int(m.group(1)), int(m.group(2))) if m else None


def _score_options(prediction):
    out = []
    for option in prediction.get("score_options") or []:
        try:
            pair = (int(option["home"]), int(option["away"]))
        except (KeyError, TypeError, ValueError):
            continue
        if pair not in out:
            out.append(pair)
    for h, a in re.findall(r"(\d+)\s*[-:：]\s*(\d+)", str(prediction.get("scores") or "")):
        pair = (int(h), int(a))
        if pair not in out:
            out.append(pair)
    return out


def _outcome_from_score(pair):
    if not pair:
        return None
    h, a = pair
    if h > a:
        return "HOME"
    if h < a:
        return "AWAY"
    return "DRAW"


def _predicted_outcome(item):
    research = item.get("research_prediction") or {}
    probs = research.get("page_probability") or {}
    if all(k in probs for k in ("home", "draw", "away")):
        return max(("home", "draw", "away"), key=lambda k: probs.get(k, -1)).upper()

    pred = research.get("page_prediction") or {}
    single = str(pred.get("single") or "").strip()
    mapping = {
        "主": "HOME", "主胜": "HOME", "home": "HOME",
        "平": "DRAW", "平局": "DRAW", "draw": "DRAW",
        "客": "AWAY", "客胜": "AWAY", "away": "AWAY",
    }
    mapped = mapping.get(single.lower()) or mapping.get(single)
    if mapped:
        return mapped
    options = _score_options(pred)
    return _outcome_from_score(options[0]) if options else None


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


def _goal_prediction_values(prediction):
    explicit = str(prediction.get("total_goals") or "").strip()
    if re.fullmatch(r"\d+", explicit):
        return {int(explicit)}
    options = _score_options(prediction)
    return {h + a for h, a in options} if options else set()


def attribute_errors(joined):
    rows = []
    summary = {
        "matches": 0,
        "wdl": {"evaluable": 0, "hits": 0},
        "score_exact": {"evaluable": 0, "hits": 0},
        "score_top2": {"evaluable": 0, "hits": 0},
        "htft": {"evaluable": 0, "hits": 0},
        "htft_top2": {"evaluable": 0, "hits": 0},
        "goals": {"evaluable": 0, "hits": 0},
    }

    for item in joined or []:
        label = item.get("result_label") or {}
        research = item.get("research_prediction") or {}
        pred = research.get("page_prediction") or {}
        row = {
            "date": item.get("date"),
            "match_id": item.get("match_id"),
            "league": item.get("league"),
            "home_team": item.get("home_team") or item.get("home"),
            "away_team": item.get("away_team") or item.get("away"),
            "sources": {
                "score": pred.get("score_source") or "RAW_OR_UNKNOWN",
                "htft": pred.get("htft_source") or "RAW_OR_UNKNOWN",
                "goals": pred.get("total_goals_source") or "RAW_OR_UNKNOWN",
            },
            "errors": [],
        }
        summary["matches"] += 1

        actual_outcome = str(label.get("actual_outcome") or label.get("result") or "").upper()
        predicted_outcome = _predicted_outcome(item)
        if actual_outcome in {"HOME", "DRAW", "AWAY"} and predicted_outcome:
            summary["wdl"]["evaluable"] += 1
            hit = predicted_outcome == actual_outcome
            summary["wdl"]["hits"] += int(hit)
            row["wdl"] = "HIT" if hit else "MISS"
            if not hit:
                row["errors"].append("WDL_MISS")

        actual_score = _score_pair(label.get("actual_score") or label.get("full_score"))
        options = _score_options(pred)
        if actual_score and options:
            summary["score_exact"]["evaluable"] += 1
            summary["score_top2"]["evaluable"] += 1
            exact = actual_score == options[0]
            top2 = actual_score in options[:2]
            summary["score_exact"]["hits"] += int(exact)
            summary["score_top2"]["hits"] += int(top2)
            row["score_exact"] = "HIT" if exact else "MISS"
            row["score_top2"] = "HIT" if top2 else "MISS"
            if not exact:
                row["errors"].append("SCORE_EXACT_MISS")
            if not top2:
                row["errors"].append("SCORE_TOP2_MISS")

        half = label.get("actual_half_score") or label.get("half_score")
        full = label.get("actual_score") or label.get("full_score")
        actual_htft = build_htft(half, full) if half and full else None
        predicted_htft = pred.get("htft_normalized") or _normalize_htft(pred.get("htft"))
        if actual_htft and predicted_htft:
            summary["htft"]["evaluable"] += 1
            hit = predicted_htft == actual_htft
            summary["htft"]["hits"] += int(hit)
            row["htft"] = "HIT" if hit else "MISS"
            top2 = []
            for value in pred.get("htft_top2") or [predicted_htft]:
                norm = _normalize_htft(value)
                if norm and norm not in top2:
                    top2.append(norm)
            summary["htft_top2"]["evaluable"] += 1
            top2_hit = actual_htft in top2[:2]
            summary["htft_top2"]["hits"] += int(top2_hit)
            row["htft_top2"] = "HIT" if top2_hit else "MISS"
            if not hit:
                row["errors"].append("HTFT_MISS")
            if not top2_hit:
                row["errors"].append("HTFT_TOP2_MISS")

        actual_goals = label.get("actual_total_goals", label.get("goals"))
        predicted_goals = _goal_prediction_values(pred)
        if actual_goals is not None and predicted_goals:
            try:
                actual_goals = int(actual_goals)
            except (TypeError, ValueError):
                actual_goals = None
            if actual_goals is not None:
                summary["goals"]["evaluable"] += 1
                hit = actual_goals in predicted_goals
                summary["goals"]["hits"] += int(hit)
                row["goals"] = "HIT" if hit else "MISS"
                if not hit:
                    row["errors"].append("GOALS_MISS")

        rows.append(row)

    for metric in summary.values():
        if isinstance(metric, dict) and "evaluable" in metric:
            n = metric["evaluable"]
            metric["accuracy"] = metric["hits"] / n if n else None

    return {"summary": summary, "matches": rows}
