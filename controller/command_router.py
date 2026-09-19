import re
from collector.url_builder import validate_date

PATTERN = re.compile(r"^预测\s+(\d{4}-\d{2}-\d{2})(?:\s+全部比赛)?$")

def parse_command(text: str):
    match = PATTERN.fullmatch(text.strip())
    if not match:
        raise ValueError("命令格式应为：预测 YYYY-MM-DD 全部比赛")
    return {"mode": "prediction", "date": validate_date(match.group(1))}
