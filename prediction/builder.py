"""HH520 Stable V3.2 deterministic prediction assembly.

WDL, HTFT and score are produced locally from the frozen V3.2 artifact.
Optional GPT is explanation/review only and cannot alter model outputs.
"""
import re
from analysis.match_analysis import analyze_match

MISSING = "未提供"
DIRECTIONS = {"home": "主胜", "draw": "平", "away": "客胜"}
SCORE = re.compile(r"(\d{1,2})[:：-](\d{1,2})")


def _score_direction(text):
    match = SCORE.fullmatch(str(text).strip())
    if not match:
        return None
    home, away = map(int, match.groups())
    return "主胜" if home > away else "客胜" if home < away else "平"


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
        "confidence_tier": "PASS",
        "status": "PASS",
        "reason": "无有效市场概率",
        "direction": None,
        "stable_version": "HH520 Stable V3.2",
    }
    if SCORE.search(str(match.get("result", ""))):
        result.update(status="SKIP", reason="已有比分，不作为赛前预测")
        return result

    analysis = analyze_match(match)
    probability = analysis["probability"]
    direction = DIRECTIONS.get(probability.get("direction"))
    result["direction"] = direction
    result["decision_filter"] = analysis["decision"]
    result["stable_v32_direction"] = direction
    result["stable_v32_decision"] = analysis["decision"].get("decision", "PASS")
    result["confidence"] = analysis["confidence"]
    result["confidence_tier"] = analysis["research_confidence"].get("tier", "PASS")
    result["market_probability"] = analysis["research_confidence"].get("pmax", 0.0)
    result["selection_status"] = analysis["decision"].get("decision", "PASS")

    if not probability.get("valid") or not direction:
        return result

    htft_top = analysis["htft"].get("top", [])
    score_top = analysis["score"].get("top_scores", [])
    if len(htft_top) < 2 or len(score_top) < 2:
        result.update(status="PASS", reason="冻结模型输出不完整")
        return result

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
        lambda_home=analysis["score"].get("lambda_home"),
        lambda_away=analysis["score"].get("lambda_away"),
        htft_model=analysis["htft"].get("model"),
        score_model=analysis["score"].get("model"),
        status="PREDICTED",
        reason=(
            "S级高置信市场方向"
            if analysis["research_confidence"].get("high_confidence")
            else "市场方向；未达到S级筛选阈值"
        ),
    )

    score_dirs = {_score_direction(result["score1"]), _score_direction(result["score2"])}
    if direction not in score_dirs:
        result["consistency_warning"] = "比分Top2与WDL主方向未形成同向候选；保留各模型原始排序"
    else:
        result["consistency_warning"] = None
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
            "page_probability_audit_only": match.get("page_probability"),
            "research_factors": match.get("research_factors", {}),
            "analysis": {
                "probability": analysis["probability"],
                "research_confidence": analysis["research_confidence"],
                "decision": analysis["decision"],
                "confidence": analysis["confidence"],
                "htft": analysis["htft"],
                "score": analysis["score"],
            },
            "locked_prediction": {
                key: prepared[key] for key in (
                    "direction", "score1", "score2", "htft1", "htft2",
                    "total_goals", "confidence", "confidence_tier",
                )
            },
            "stable_version": "HH520 Stable V3.2",
            "source_contract": "HH520_10027s",
            "excluded_source_fields": ["建议下注", "是否下注", "page_prediction"],
            "gpt_role": "EXPLANATION_ONLY",
        })
    return payload


def validate_prediction(item, prepared, evidence):
    if item["match_id"] != prepared["match_id"]:
        raise ValueError("GPT 场次ID或顺序不匹配")

    # GPT is explanation-only. Any attempted change is ignored instead of
    # invalidating the deterministic Stable prediction.
    locked = ("direction", "score1", "score2", "htft1", "htft2", "total_goals")
    rejected = [
        key for key in locked
        if item.get(key) != prepared.get(key)
    ]

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
