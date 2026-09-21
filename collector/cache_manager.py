from pathlib import Path
import json
import os
import tempfile
from .url_builder import validate_date

CACHE_DIR = Path(__file__).resolve().parents[1] / "cache"

def _source_token(source: str) -> str:
    value = str(source or "10023s").strip().lower()
    if value not in {"10023s", "10027s"}:
        raise ValueError("未知 HH520 缓存源")
    return value

def cache_path(date: str, source: str = "10023s") -> Path:
    validate_date(date)
    source = _source_token(source)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{source}_{date}.json"

def load_cache(date: str, source: str = "10023s"):
    path = cache_path(date, source)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("date") != date:
            raise ValueError("日期或结构不匹配")
        return payload
    except (ValueError, OSError) as exc:
        raise ValueError("本地缓存损坏；停止抓取以避免重复扣费，请恢复缓存") from exc

def save_cache(date: str, payload, source: str = "10023s"):
    path = cache_path(date, source)
    if payload.get("date") != date:
        raise ValueError("缓存日期不匹配")
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return path

def claim_request(date: str, source: str = "10023s", allow_resume_incomplete: bool = False):
    """Exclusive ledger per source/date.

    A successful cache always wins. An existing .requested marker may only be
    resumed when explicitly allowed and when no cache exists. This is intended
    for serialized GitHub Research recovery after a transient 429, not for
    arbitrary force-refresh behavior.
    """
    data_path = cache_path(date, source)
    path = data_path.with_suffix(".requested")
    try:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(f"Request reserved for {source}; do not delete to retry. Restore/import captured raw data.\n")
        return "CLAIMED"
    except FileExistsError as exc:
        if allow_resume_incomplete and not data_path.exists():
            return "RESUMED_INCOMPLETE"
        raise RuntimeError("此日期和数据源已抓取或有未完成请求；禁止重复抓取。可导入已保存的响应。") from exc
