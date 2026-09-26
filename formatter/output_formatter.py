OUTPUT_COLUMNS = ["球队对阵","胜平负场景","市场概率","比分×2及概率","半全场×2及概率","总进球及概率"]

STATE_ZH = {"CONFIRM":"确认","BALANCED":"均衡","TAIL_ALERT":"尾部预警","PASS":"回避"}


def _pct(value):
    if value is None:
        return "未提供"
    try:
        return f"{float(value)*100:.1f}%"
    except (TypeError, ValueError):
        return "未提供"


def _scenario(pred):
    primary = pred.get("direction") or "未提供"
    if primary == "均衡":
        return "均衡（不强制方向）"
    state = pred.get("state")
    label = STATE_ZH.get(state)
    return f"{primary}（{label}）" if label else primary


def build_display_row(pred: dict) -> dict:
    get=pred.get
    return {
        "球队对阵": f"{pred['home_team']} vs {pred['away_team']} [{'全数据' if pred.get('data_mode') == 'FULL_DATA' else '10027'}]",
        "胜平负场景": _scenario(pred),
        "市场概率": _pct(get("market_probability")),
        "比分×2及概率": f"{get('score1') or '未提供'} ({_pct(get('score1_probability'))}) / {get('score2') or '未提供'} ({_pct(get('score2_probability'))})",
        "半全场×2及概率": f"{get('htft1') or '未提供'} ({_pct(get('htft1_probability'))}) / {get('htft2') or '未提供'} ({_pct(get('htft2_probability'))})",
        "总进球及概率": f"{get('total_goals') or '未提供'} ({_pct(get('total_goals_probability'))})",
    }


def build_output_contract(predictions: list[dict]) -> dict:
    return {
        "version": "HH520-OUTPUT-V3.5.1", "stable_version": "HH520 Stable V3.5.1",
        "strict": True, "required_columns": OUTPUT_COLUMNS,
        "display_rows": [build_display_row(pred) for pred in predictions],
        "render_rule": "必须按6列完整输出；球队对阵后必须标注[全数据]或[10027]；全数据=双方外部SHOTS+RESULT_STABILITY+HALF_TIMING均满足质量门槛并已进入FT/比分/HTFT；10027=外部数据不完整，完全回退10027基础链路。",
    }


def format_prediction(pred: dict) -> str:
    get=pred.get
    return (
        f"比赛：\n{pred['home_team']} vs {pred['away_team']}\n\n"
        f"胜平负场景：{_scenario(pred)}\n市场概率：{_pct(get('market_probability'))}\n"
        f"模型概率：{_pct(get('model_probability'))}\nFT等级：{get('ft_grade','未提供')}\n风险等级：{get('risk_tier','未提供')}\n\n"
        f"比分预测：\n1. {get('score1') or '未提供'} ({_pct(get('score1_probability'))})\n"
        f"2. {get('score2') or '未提供'} ({_pct(get('score2_probability'))})\n\n"
        f"半全场：\n1. {get('htft1') or '未提供'} ({_pct(get('htft1_probability'))})\n"
        f"2. {get('htft2') or '未提供'} ({_pct(get('htft2_probability'))})\n\n"
        f"总进球：{get('total_goals') or '未提供'} ({_pct(get('total_goals_probability'))})\n"
        f"原因：{get('reason','资料不足')}"
    )
