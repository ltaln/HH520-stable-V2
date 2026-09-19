from pathlib import Path
import json
import os
import tempfile
from .url_builder import validate_date

CACHE_DIR = Path(__file__).resolve().parents[1] / "cache"

def cache_path(date: str) -> Path:
    validate_date(date)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"10023s_{date}.json"

def load_cache(date: str):
    path = cache_path(date)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("date") != date:
            raise ValueError("日期或结构不匹配")
        return payload
    except (ValueError, OSError) as exc:
        raise ValueError("本地缓存损坏；停止抓取以避免重复扣费，请恢复缓存") from exc

def save_cache(date: str, payload):
    path = cache_path(date)
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

def claim_request(date: str):
    """Permanent exclusive ledger: uncertainty/failure must not cause a second call."""
    path = cache_path(date).with_suffix(".requested")
    try:
        with path.open("x", encoding="utf-8") as stream:
            stream.write("Request reserved; do not delete to retry. Restore/import captured raw data.\n")
    except FileExistsError as exc:
        raise RuntimeError("此日期已抓取或有未完成请求；禁止重复抓取。可导入已保存的响应。") from exc
