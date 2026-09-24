"""HH520 Stable V3.5 Phase 1 deterministic prediction assembly."""
import re
from analysis.match_analysis import analyze_match

MISSING = "未提供"
DIRECTIONS = {"home": "主胜", "draw": "平", "away": "客胜"}
STATE_ZH = {"CONFIRM":"确认","BALANCED":"均衡","TAIL_ALERT":"尾部预警","PASS":"回避"}
SCORE = re.compile(r"(\d{1,2})[:：-](\d{1,2})")


def prepare_match(match):
    result = {
        "match_id": str(match.get("match_id", "")),
        "home_team": match["home_team"], "away_team": match["away_team"],
        "score1": MISSING, "score2": MISSING, "htft1": MISSING, "htft2": MISSING,
        "total_goals": MISSING, "confidence": 0, "status": "PASS",
        "reason": "无有效市场概率", "direction": None, "alternate_direction": None,
        "state": "PASS", "stable_version": "HH520 Stable V3.5 Phase 1",
    }
    if SCORE.search(str(match.get("result", ""))):
        result.update(status="SKIP", reason="已有比分，不作为赛前预测")
        return result

    analysis = analyze_match(match)
    probability = analysis["probability"]
    decision = analysis["decision"]
    consistency = analysis["consistency"]
    primary = probability.get("direction")
    raw_direction = DIRECTIONS.get(primary)
    probs = probability.get("probabilities") or {}
    ordered = sorted(probs, key=lambda k: float(probs[k]), reverse=True) if probs else []
    authorized = bool(decision.get("ft_direction_authorized", True))
    direction = raw_direction
    if primary in {"home", "away"} and not authorized:
        direction = "均衡"

    effective_tier = consistency.get("effective_decision", decision.get("decision", "PASS"))

    result.update(
        direction=direction,
        raw_direction=raw_direction,
        alternate_direction=DIRECTIONS.get(ordered[1]) if len(ordered) > 1 else None,
        state=effective_tier,
        base_state=decision.get("decision", "PASS"),
        state_label=STATE_ZH.get(effective_tier, effective_tier),
        decision_filter=decision,
        ft_grade=decision.get("ft_grade"),
        ft_direction_authorized=authorized,
        stable_v35_raw_direction=raw_direction,
        confidence=analysis["confidence"],
        ft_confidence=probs.get(primary) if primary else None,
        market_probability=(probability.get("market_probabilities") or {}).get(primary) if primary else None,
        model_probability=probs.get(primary) if primary else None,
        draw_anchor=probability.get("draw_anchor"),
        home_share=probability.get("home_share"),
        risk_tier=effective_tier,
        risk_score=decision.get("risk_score"),
        page_probability=probability.get("page_probability"),
        tail_alert=effective_tier in {"TAIL_ALERT","PASS"},
        draw_candidate=primary == "draw",
        calibration=analysis["calibration"],
        timing_used=False, timing_source=None,
        quality_warnings=analysis["quality"].get("warnings", []),
        cross_gate=consistency.get("cross_gate"),
    )

    if not probability.get("valid") or not raw_direction:
        return result

    htft_top = consistency.get("htft_top", [])
    score_top = consistency.get("score_top", [])
    if len(score_top) < 2:
        result.update(status="PASS", reason="V3.5 Phase 1 独立比分输出不完整")
        return result

    totals = analysis["score"].get("top_totals", [])
    total_pick = totals[0] if totals else None

    # Low-probability FT is no longer allowed to cascade into a formal HT/FT pick.
    htft_available = authorized and len(htft_top) >= 2

    result.update(
        score1=score_top[0]["score"], score2=score_top[1]["score"],
        score1_probability=score_top[0]["probability"], score2_probability=score_top[1]["probability"],
        htft1=htft_top[0]["selection"] if htft_available else MISSING,
        htft2=htft_top[1]["selection"] if htft_available else MISSING,
        htft1_probability=htft_top[0]["probability"] if htft_available else None,
        htft2_probability=htft_top[1]["probability"] if htft_available else None,
        total_goals=analysis["score"].get("total_goals_pick") or MISSING,
        total_goals_probability=(total_pick or {}).get("probability"),
        lambda_home=analysis["score"].get("lambda_home"),
        lambda_away=analysis["score"].get("lambda_away"),
        high_score_mass=analysis["score"].get("high_score_mass"),
        tail_score_candidates=analysis["score"].get("tail_scores", [])[:2],
        htft_model=analysis["htft"].get("model"),
        score_model=analysis["score"].get("model"),
        consistency=consistency,
        status="PREDICTED",
    )

    cross_status = (consistency.get("cross_gate") or {}).get("status")
    if not authorized and primary in {"home", "away"}:
        result["reason"] = "FT模型概率低于55%，不强制主胜/客胜；比分保持独立输出，HT/FT暂不正式输出"
    elif cross_status == "CONFLICT":
        result["reason"] = "FT与独立比分方向冲突，Cross-Layer Gate已自动降级"
    else:
        result["reason"] = {
            "CONFIRM": "FT通过可靠性过滤，且未发现需要进一步降级的跨层冲突",
            "BALANCED": "FT保留但可靠度有限，按均衡处理",
            "TAIL_ALERT": "FT方向存在明显尾部或跨层风险",
            "PASS": "当前结构仅供参考，不作为强方向",
        }.get(effective_tier, "V3.5 Phase 1结构输出")
    return result


def build_model_input(matches):
    payload = []
    for match in matches:
        prepared = prepare_match(match)
        if prepared["status"] != "PREDICTED":
            continue
        analysis = analyze_match(match)
        payload.append({
            "match_id": prepared["match_id"], "home_team": prepared["home_team"],
            "away_team": prepared["away_team"], "league": match.get("league"),
            "kickoff": match.get("kickoff"), "market": match.get("market", {}),
            "research_factors": match.get("research_factors", {}),
            "analysis": {k: analysis[k] for k in ("probability","decision","calibration","consistency","htft","score")},
            "locked_prediction": {key: prepared[key] for key in (
                "direction","alternate_direction","state","score1","score2","htft1","htft2","total_goals")},
            "stable_version": "HH520 Stable V3.5 Phase 1",
            "source_contract": "HH520_10027s_ONLY",
            "excluded_source_fields": ["建议下注","是否下注","page_prediction"],
            "gpt_role": "EXPLANATION_ONLY",
        })
    return payload


def validate_prediction(item, prepared, evidence):
    if item["match_id"] != prepared["match_id"]:
        raise ValueError("GPT 场次ID或顺序不匹配")
    locked = ("direction","alternate_direction","state","score1","score2","htft1","htft2","total_goals")
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
    eligible = [i for i,row in enumerate(prepared) if row["status"] == "PREDICTED"]
    if not use_gpt or not eligible:
        return prepared
    from .gpt import request_predictions
    payload = build_model_input(matches)
    enriched = request_predictions(payload)
    if len(enriched) != len(eligible):
        raise ValueError("GPT 返回比赛数量不匹配")
    for index,item,evidence in zip(eligible,enriched,payload):
        prepared[index] = validate_prediction(item,prepared[index],evidence)
    return prepared
