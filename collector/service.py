import os
from datetime import datetime, timezone

from .url_builder import build_10027s_url
from .cache_manager import load_cache, save_cache, claim_request
from .firecrawl_client import scrape_markdown, require_key
from .hh520_10027_parser import parse_10027s_markdown

SOURCE = "10027s"
SOURCE_NAME = "HH520_10027s"


def _source_config(date, source=SOURCE):
    normalized = str(source or SOURCE).lower()
    if normalized != SOURCE:
        raise ValueError("Stable V3 只允许 HH520 10027s 数据源")
    return {
        "source": SOURCE,
        "source_name": SOURCE_NAME,
        "url": build_10027s_url(date, date),
        "parser": parse_10027s_markdown,
    }


def validate_raw(date, raw, source=SOURCE):
    cfg = _source_config(date, source)
    url = cfg["url"]
    if not isinstance(raw, dict) or raw.get("success") is not True:
        raise ValueError("需要成功的 Firecrawl 响应 {success:true,data:{markdown,metadata}}")
    data = raw.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("markdown"), str):
        raise ValueError("Firecrawl 缺少 markdown")
    metadata = data.get("metadata") or {}
    source_url = metadata.get("sourceURL") or metadata.get("url")
    if source_url != url:
        raise ValueError("响应来源或日期不匹配固定10027s URL")
    if metadata.get("statusCode", 200) != 200:
        raise ValueError("页面HTTP状态异常")
    return data["markdown"]


def import_response(date, raw, source=SOURCE):
    cfg = _source_config(date, source)
    validate_raw(date, raw, source=cfg["source"])
    if load_cache(date, source=SOURCE) is not None:
        raise ValueError("该日期已有10027s缓存，不覆盖")
    payload = {
        "date": date,
        "url": cfg["url"],
        "source": SOURCE_NAME,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "raw": raw,
    }
    try:
        claim_request(date, source=SOURCE)
    except RuntimeError:
        pass
    save_cache(date, payload, source=SOURCE)
    return collect_date(date)


def collect_date(date: str, force_refresh: bool = False, source: str = SOURCE):
    cfg = _source_config(date, source)
    if force_refresh:
        raise ValueError("禁止 force_refresh；同日期只允许一次10027s抓取")

    payload = load_cache(date, source=SOURCE)
    if payload is None:
        require_key()
        allow_resume = os.getenv("HH520_ALLOW_INCOMPLETE_REQUEST_RESUME", "").strip() == "1"
        claim_request(date, source=SOURCE, allow_resume_incomplete=allow_resume)
        raw = scrape_markdown(cfg["url"])
        payload = {
            "date": date,
            "url": cfg["url"],
            "source": SOURCE_NAME,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "raw": raw,
        }
        save_cache(date, payload, source=SOURCE)

    markdown = validate_raw(date, payload.get("raw"), source=SOURCE)
    payload["matches"] = parse_10027s_markdown(markdown)
    return payload
