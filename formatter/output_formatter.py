OUTPUT_COLUMNS = [
    "球队对阵",
    "胜平负",
    "市场概率",
    "置信等级",
    "比分×2",
    "半全场×2",
    "总进球",
    "置信度",
    "最终筛选",
]


def _pct(value):
    if value is None:
        return "未提供"
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "未提供"


def build_display_row(pred: dict) -> dict:
    get = pred.get
    decision = get("decision_filter") or {}
    filter_decision = get("stable_v32_decision") or decision.get("decision") or "PASS"
    confidence = get("confidence")
    confidence_text = "未提供" if confidence is None else f"{confidence}%"
    return {
        "球队对阵": f"{pred['home_team']} vs {pred['away_team']}",
        "胜平负": get("direction") or "未提供",
        "市场概率": _pct(get("market_probability")),
        "置信等级": get("confidence_tier") or "PASS",
        "比分×2": f"{get('score1') or '未提供'} / {get('score2') or '未提供'}",
        "半全场×2": f"{get('htft1') or '未提供'} / {get('htft2') or '未提供'}",
        "总进球": get("total_goals") or "未提供",
        "置信度": confidence_text,
        "最终筛选": filter_decision,
    }


def build_output_contract(predictions: list[dict]) -> dict:
    return {
        "version": "HH520-OUTPUT-V3.2",
        "stable_version": "HH520 Stable V3.2",
        "strict": True,
        "required_columns": OUTPUT_COLUMNS,
        "display_rows": [build_display_row(pred) for pred in predictions],
        "render_rule": "必须完整输出全部9列；禁止退回旧版5列简表；不得省略胜平负、市场概率、置信等级或最终筛选。",
    }


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
