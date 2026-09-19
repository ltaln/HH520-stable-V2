from datetime import date as calendar_date
import re
from urllib.parse import urlencode

BASE_URL = "https://www.hh520.com/tx/10023s.php"

def validate_date(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("日期必须为 YYYY-MM-DD")
    calendar_date.fromisoformat(value)
    return value

def build_10023s_url(date: str, threshold: int = 1, bankroll: int = 5000) -> str:
    validate_date(date)
    if threshold != 1 or bankroll != 5000:
        raise ValueError("Stable 固定 threshold=1、bankroll=5000")
    return f"{BASE_URL}?{urlencode({'riqi': date, 'threshold': 1, 'bankroll': 5000})}"
