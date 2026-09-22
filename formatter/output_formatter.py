OUTPUT_COLUMNS = [
    "球队对阵",
    "胜平负场景",
    "市场概率",
    "比分×2及概率",
    "半全场×2及概率",
    "总进球及概率",
]

STATE_ZH = {
    "CONFIRMED": "确认",
    "STANDARD": "标准",
    "BALANCED": "均衡",
    "CONFLICT": "冲突",
    "TAIL_ALERT": "尾部预警",
}


def _pct(value):
    if value is None:
        return "未提供"
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "未提供"


def _scenario(pred):
    primary = pred.get("direction") or "未提供"
    alternate = pred.get("alternate_direction")
    state = pred.get("state")
    if alternate and alternate != primary and state in {"BALANCED", "CONFLICT", "TAIL_ALERT"}:
        return f"{primary} / {alternate}（{STATE_ZH.get(state, state)}）"
    if state == "CONFIRMED":
        return f"{primary}（确认）"
    return primary


def build_display_row(pred: dict) -> dict:
    get = pred.get
    return {
        "球队对阵": f"{pred['home_team']} vs {pred['away_team']}",
        "胜平负场景": _scenario(pred),
        "市场概率": _pct(get("market_probability")),
        "比分×2及概率": (
            f"{get('score1') or '未提供'} ({_pct(get('score1_probability'))}) / "
            f"{get('score2') or '未提供'} ({_pct(get('score2_probability'))})"
        ),
        "半全场×2及概率": (
            f"{get('htft1') or '未提供'} ({_pct(get('htft1_probability'))}) / "
            f"{get('htft2') or '未提供'} ({_pct(get('htft2_probability'))})"
        ),
        "总进球及概率": f"{get('total_goals') or '未提供'} ({_pct(get('total_goals_probability'))})",
    }


def build_output_contract(predictions: list[dict]) -> dict:
    return {
        "version": "HH520-OUTPUT-V3.3",
        "stable_version": "HH520 Stable V3.3",
        "strict": True,
        "required_columns": OUTPUT_COLUMNS,
        "display_rows": [build_display_row(pred) for pred in predictions],
        "render_rule": "必须按6列完整输出；不得显示置信等级、置信度或最终筛选；不得把主场景和尾部场景混成同一级单一方向。",
    }


def format_prediction(pred: dict) -> str:
    get = pred.get
    timing = "已使用" if get("timing_used") else "未使用/未获得"
    return (
        f"比赛：\n{pred['home_team']} vs {pred['away_team']}\n\n"
        f"胜平负场景：{_scenario(pred)}\n"
        f"市场概率：{_pct(get('market_probability'))}\n\n"
        f"比分预测：\n"
        f"1. {get('score1') or '未提供'} ({_pct(get('score1_probability'))})\n"
        f"2. {get('score2') or '未提供'} ({_pct(get('score2_probability'))})\n\n"
        f"半全场：\n"
        f"1. {get('htft1') or '未提供'} ({_pct(get('htft1_probability'))})\n"
        f"2. {get('htft2') or '未提供'} ({_pct(get('htft2_probability'))})\n"
        f"分时数据：{timing}\n\n"
        f"总进球：{get('total_goals') or '未提供'} ({_pct(get('total_goals_probability'))})\n"
        f"状态：{get('state', '未提供')}\n"
        f"原因：{get('reason', '资料不足')}"
    )
