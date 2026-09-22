"""HH520 Stable V3.3 deterministic prediction assembly.

WDL is market-anchored, then State/Conflict/Tail logic determines how the
primary and alternate scenarios are presented. GPT remains explanation-only.
"""
import re
from analysis.match_analysis import analyze_match

MISSING = "未提供"
DIRECTIONS = {"home": "主胜", "draw": "平", "away": "客胜"}
STATE_ZH = {
    "CONFIRMED": "确认",
    "STANDARD": "标准",
    "BALANCED": "均衡",
    "CONFLICT": "冲突",
    "TAIL_ALERT": "尾部预警",
    "INVALID": "无效",
}
SCORE = re.compile(r"(\d{1,2})[:：-](\d{1,2})")


def prepare_match(match):
    result = {
        "match_id": str(match.get("match_id", "")),
        "home_team": match["home_team"],
        "away_team": match["away_team"],
        "score1": MISSING,
        "score2": MISSING,
        "htft1": MISSING,
        "htft2": MISSING,
        "total_goals": MISSING,
        "confidence": 0,
        "status": "PASS",
        "reason": "无有效市场概率",
        "direction": None,
        "alternate_direction": None,
        "state": "INVALID",
        "stable_version": "HH520 Stable V3.3",
    }
    if SCORE.search(str(match.get("result", ""))):
        result.update(status="SKIP", reason="已有比分，不作为赛前预测")
        return result

    analysis = analyze_match(match)
    probability = analysis["probability"]
    state = analysis["state"]
    primary = state.get("primary_direction") or probability.get("direction")
    direction = DIRECTIONS.get(primary)
    alternate = DIRECTIONS.get(state.get("alternate_direction"))

    result.update(
        direction=direction,
        alternate_direction=alternate,
        state=state.get("state", "INVALID"),
        base_state=state.get("base_state", "INVALID"),
        state_label=STATE_ZH.get(state.get("state"), state.get("state")),
        decision_filter=analysis["decision"],
        stable_v33_direction=direction,
        stable_v33_decision=analysis["decision"].get("decision", "PASS"),
        confidence=analysis["confidence"],
        market_probability=state.get("market_pmax") or probability.get("pmax") or 0.0,
        page_probability=probability.get("page_probability"),
        tail_alert=bool(state.get("tail_alert")),
        draw_candidate=bool(state.get("draw_candidate")),
        calibration=analysis["calibration"],
        timing_used=bool(analysis["htft"].get("timing_used")),
        timing_source=analysis["htft"].get("timing_source"),
        quality_warnings=analysis["quality"].get("warnings", []),
    )

    if not probability.get("valid") or not direction:
        return result

    htft_top = analysis["consistency"].get("htft_top", [])
    score_top = analysis["consistency"].get("score_top", [])
    if len(htft_top) < 2 or len(score_top) < 2:
        result.update(status="PASS", reason="V3.3 场景一致性输出不完整")
        return result

    totals = analysis["score"].get("top_totals", [])
    total_pick = totals[0] if totals else None

    result.update(
        score1=score_top[0]["score"],
        score2=score_top[1]["score"],
        score1_probability=score_top[0]["probability"],
        score2_probability=score_top[1]["probability"],
        htft1=htft_top[0]["selection"],
        htft2=htft_top[1]["selection"],
        htft1_probability=htft_top[0]["probability"],
        htft2_probability=htft_top[1]["probability"],
        total_goals=analysis["score"].get("total_goals_pick") or MISSING,
        total_goals_probability=(total_pick or {}).get("probability"),
        lambda_home=analysis["score"].get("lambda_home"),
        lambda_away=analysis["score"].get("lambda_away"),
        high_score_mass=analysis["score"].get("high_score_mass"),
        tail_score_candidates=analysis["score"].get("tail_scores", [])[:2],
        htft_model=analysis["htft"].get("model"),
        score_model=analysis["score"].get("model"),
        consistency=analysis["consistency"],
        status="PREDICTED",
    )

    base = result.get("base_state")
    if result["tail_alert"]:
        result["reason"] = "市场方向保留为主场景；检测到冲突/尾部结构，第二场景独立展示"
    elif base == "BALANCED":
        result["reason"] = "均衡场；不把市场最高项描述为强方向，保留第二场景"
    elif base == "CONFLICT":
        result["reason"] = "市场与独立结构存在冲突；保留市场主锚并降级为多场景"
    elif base == "CONFIRMED":
        result["reason"] = "市场主方向得到历史稳定结构确认"
    else:
        result["reason"] = "市场主方向；未触发强确认或强冲突"

    return result


def build_model_input(matches):
    """Build GPT review payload. Model outputs are locked and cannot be changed."""
    payload = []
    for match in matches:
        prepared = prepare_match(match)
        if prepared["status"] != "PREDICTED":
            continue
        analysis = analyze_match(match)
        payload.append({
            "match_id": prepared["match_id"],
            "home_team": prepared["home_team"],
            "away_team": prepared["away_team"],
            "league": match.get("league"),
            "kickoff": match.get("kickoff"),
            "market": match.get("market", {}),
            "page_probability_for_state": match.get("page_probability"),
            "research_factors": match.get("research_factors", {}),
            "goal_timing": match.get("goal_timing", {}),
            "analysis": {
                "probability": analysis["probability"],
                "state": analysis["state"],
                "decision": analysis["decision"],
                "calibration": analysis["calibration"],
                "consistency": analysis["consistency"],
                "htft": analysis["htft"],
                "score": analysis["score"],
            },
            "locked_prediction": {
                key: prepared[key] for key in (
                    "direction", "alternate_direction", "state",
                    "score1", "score2", "htft1", "htft2", "total_goals",
                )
            },
            "stable_version": "HH520 Stable V3.3",
            "source_contract": "HH520_10027s+PUBLIC_GOAL_TIMING_OPTIONAL",
            "excluded_source_fields": ["建议下注", "是否下注", "page_prediction"],
            "gpt_role": "EXPLANATION_ONLY",
        })
    return payload


def validate_prediction(item, prepared, evidence):
    if item["match_id"] != prepared["match_id"]:
        raise ValueError("GPT 场次ID或顺序不匹配")

    locked = (
        "direction", "alternate_direction", "state",
        "score1", "score2", "htft1", "htft2", "total_goals",
    )
    rejected = [key for key in locked if item.get(key) != prepared.get(key)]

    result = dict(prepared)
    result["gpt_review"] = item.get("reason", "")
    result["gpt_status"] = item.get("status", "GPT")
    result["gpt_rejected_changes"] = rejected
    if item.get("status") == "PASS":
        result["status"] = "PREDICTED_GPT_REVIEW_SKIPPED"
    elif rejected:
        result["status"] = "PREDICTED_GPT_REVIEW_REJECTED"
    else:
        result["status"] = "PREDICTED_GPT_REVIEWED"
    return result


def build_predictions(matches, use_gpt=False):
    prepared = [prepare_match(match) for match in matches]
    eligible = [i for i, row in enumerate(prepared) if row["status"] == "PREDICTED"]
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
