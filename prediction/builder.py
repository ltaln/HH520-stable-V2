"""Stable V3: probability -> value -> quality -> class -> risk -> decision -> optional GPT."""
import re
from analysis.match_analysis import analyze_match

MISSING = "未提供"
DIRECTIONS = {"home": "主胜", "draw": "平", "away": "客胜"}
SCORE = re.compile(r"(\d{1,2})[:：-](\d{1,2})")
SIDE = {"主": "主胜", "胜": "主胜", "主胜": "主胜", "平": "平", "平局": "平",
        "客": "客胜", "负": "客胜", "客胜": "客胜"}


def score_direction(text):
    match = SCORE.fullmatch(str(text).strip())
    if not match:
        return None
    home, away = map(int, match.groups())
    return "主胜" if home > away else "客胜" if home < away else "平"


def valid_htft(text, direction):
    parts = str(text).strip().split("/")
    return len(parts) == 2 and parts[0] in SIDE and SIDE.get(parts[1]) == direction


def prepare_match(match):
    result = {"match_id": str(match.get("match_id", "")), "home_team": match["home_team"],
              "away_team": match["away_team"], "score1": MISSING, "score2": MISSING,
              "htft1": MISSING, "htft2": MISSING, "total_goals": MISSING,
              "confidence": 0, "status": "PASS", "reason": "无有效概率", "direction": None}
    if SCORE.search(str(match.get("result", ""))):
        result.update(status="SKIP", reason="已有比分，不作为赛前预测")
        return result
    analysis = analyze_match(match)
    result["direction"] = DIRECTIONS.get(analysis["probability"]["direction"])
    result["decision_filter"] = analysis["decision"]
    result["stable_v3_direction"] = result["direction"]
    result["stable_v3_decision"] = analysis["decision"].get("decision", "PASS")
    # Stable keeps the established GPT inference contract while recording the
    # V3 decision as an advisory/audit signal. Calibration decides later whether
    # V3 thresholds are safe enough to become a hard gate.
    if analysis["probability"].get("valid") and result["direction"]:
        result.update(status="READY_FOR_GPT", reason="有效概率；等待GPT最终推理")
    else:
        result.update(status="PASS", reason="无有效概率")
    return result


def build_model_input(matches):
    """Only pre-match evidence enters GPT; page betting/advice/recommendation fields are excluded."""
    payload = []
    for match in matches:
        prepared = prepare_match(match)
        if prepared["status"] != "READY_FOR_GPT":
            continue
        analysis = analyze_match(match)
        payload.append({
            "match_id": prepared["match_id"], "home_team": prepared["home_team"],
            "away_team": prepared["away_team"], "league": match.get("league"),
            "kickoff": match.get("kickoff"), "market": match.get("market", {}),
            "page_probability": match.get("page_probability"),
            "team_dna": match.get("team_dna", {}),
            "analysis": {
                "probability": analysis["probability"],
                "value": analysis["value"],
                "decision": analysis["decision"],
                "confidence": analysis["confidence"],
            }, "direction": prepared["direction"],
            "decision_filter": analysis["decision"],
            "stable_version": "HH520 Stable V3",
            "source_contract": "HH520_10027s",
            "excluded_source_fields": ["建议下注", "是否下注", "page_prediction"],
            "data_limitations": [
                "10027s建议下注/是否下注永不进入预测与GPT输入",
                "10027s基础表比分字段是赛果标签，历史比赛不得进入赛前推理",
                "比分/半全场/总进球必须由当前赛前证据推导，不能复制页面最终建议",
            ],
        })
    return payload


def _pass(prepared, reason):
    result = dict(prepared)
    result.update(status="PASS", confidence=0, reason=reason)
    return result


def validate_prediction(item, prepared, evidence):
    if item["match_id"] != prepared["match_id"]:
        raise ValueError("GPT 场次ID或顺序不匹配")
    if item["status"] == "PASS":
        return _pass(prepared, item["reason"])
    if item["direction"] != prepared["direction"]:
        return _pass(prepared, "GPT与Probability Layer方向冲突")
    scores = [item["score1"], item["score2"]]
    htft = [item["htft1"], item["htft2"]]
    if len(set(scores)) != 2 or any(score_direction(x) != prepared["direction"] for x in scores):
        return _pass(prepared, "GPT未提供两个不同且符合方向的比分")
    if len(set(htft)) != 2 or any(not valid_htft(x, prepared["direction"]) for x in htft):
        return _pass(prepared, "GPT未提供两个不同且符合方向的半全场")
    goals = re.fullmatch(r"(\d+)(?:\s*[-—–~至]\s*(\d+))?\s*球?", item["total_goals"].strip())
    if not goals:
        return _pass(prepared, "GPT总进球格式无效")
    low = int(goals.group(1))
    high = int(goals.group(2) or low)
    if low > high:
        return _pass(prepared, "GPT总进球区间无效")
    score_pairs = [tuple(map(int, SCORE.fullmatch(score).groups())) for score in scores]
    if any(not low <= home + away <= high for home, away in score_pairs):
        return _pass(prepared, "GPT总进球与比分冲突")
    for pick in htft:
        halftime = SIDE[pick.split("/")[0]]
        feasible = any(
            score_direction(f"{h}:{a}") == halftime
            for home, away in score_pairs
            for h in range(home + 1) for a in range(away + 1)
        )
        if not feasible:
            return _pass(prepared, "GPT半场方向与最终比分不可能同时成立")
    if not evidence.get("team_dna"):
        return _pass(prepared, "缺少进攻/防守结构数据，无法支持精细预测")
    result = dict(prepared)
    result.update(item)
    result["confidence"] = max(1, min(99, int(item["confidence"])))
    return result


def build_predictions(matches, use_gpt=False):
    prepared = [prepare_match(match) for match in matches]
    eligible = [i for i, row in enumerate(prepared) if row["status"] == "READY_FOR_GPT"]
    if not use_gpt or not eligible:
        return prepared
    from .gpt import request_predictions
    payload = build_model_input(matches)
    enriched = request_predictions(payload)
    if len(enriched) != len(eligible):
        raise ValueError("GPT 返回比赛数量不匹配")
    for index, item, evidence in zip(eligible, enriched, payload):
        prepared[index] = validate_prediction(item, prepared[index], evidence)
    return prepared
