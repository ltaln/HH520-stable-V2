from datetime import date as calendar_date
import re
from urllib.parse import urlencode

BASE_10027S_URL = "https://www.hh520.com/tx/10027s.php"


def validate_date(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("日期必须为 YYYY-MM-DD")
    calendar_date.fromisoformat(value)
    return value


def build_10027s_url(start_date: str, end_date: str = None, threshold: int = 1, bankroll: int = 5000) -> str:
    start_date = validate_date(start_date)
    end_date = validate_date(end_date or start_date)
    if end_date < start_date:
        raise ValueError("riqi_end 不能早于 riqi_start")
    if threshold != 1 or bankroll != 5000:
        raise ValueError("HH520 固定 threshold=1、bankroll=5000")
    return f"{BASE_10027S_URL}?{urlencode({'riqi_start': start_date, 'riqi_end': end_date, 'threshold': 1, 'bankroll': 5000})}"
