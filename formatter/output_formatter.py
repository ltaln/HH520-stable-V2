def _pct(value):
    if value is None:
        return "未提供"
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "未提供"


def format_prediction(pred: dict) -> str:
    get = pred.get
    decision = get("decision_filter") or {}
    filter_version = decision.get("version") or "未提供"
    filter_decision = get("stable_v32_decision") or decision.get("decision") or "PASS"
    warning = get("consistency_warning")
    warning_text = f"\n一致性提示：{warning}" if warning else ""

    return (
        f"比赛：\n{pred['home_team']} vs {pred['away_team']}\n\n"
        f"胜平负：\n{get('direction') or '未提供'}\n"
        f"市场概率：{_pct(get('market_probability'))}\n"
        f"置信等级：{get('confidence_tier') or 'PASS'}\n\n"
        f"比分预测：\n"
        f"1. {pred['score1']} ({_pct(get('score1_probability'))})\n"
        f"2. {pred['score2']} ({_pct(get('score2_probability'))})\n\n"
        f"半全场：\n"
        f"1. {pred['htft1']} ({_pct(get('htft1_probability'))})\n"
        f"2. {pred['htft2']} ({_pct(get('htft2_probability'))})\n\n"
        f"总进球：\n{pred['total_goals']}\n\n"
        f"置信度：{pred['confidence']}%\n"
        f"最终筛选：{filter_decision}\n"
        f"Filter版本：{filter_version}\n"
        f"状态：{get('status', 'PASS')}\n"
        f"原因：{get('reason', '资料不足')}"
        f"{warning_text}"
    )
