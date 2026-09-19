def format_prediction(pred: dict) -> str:
    get = pred.get
    return (
        f"比赛：\n{pred['home_team']} vs {pred['away_team']}\n\n"
        f"比分预测：\n1. {pred['score1']}\n2. {pred['score2']}\n\n"
        f"半全场：\n1. {pred['htft1']}\n2. {pred['htft2']}\n\n"
        f"总进球：\n{pred['total_goals']}\n\n"
        f"方向：\n{get('direction') or '未提供'}\n\n"
        f"置信度：\n{pred['confidence']}%\n"
        f"状态：{get('status', 'PASS')}\n"
        f"原因：{get('reason', '资料不足')}"
    )
