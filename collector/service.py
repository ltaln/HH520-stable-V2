from datetime import datetime, timezone

from .url_builder import build_10023s_url, build_10027s_url
from .cache_manager import load_cache, save_cache, claim_request
from .firecrawl_client import scrape_markdown, require_key
from .hh520_parser import parse_10023s_markdown
from .hh520_10027_parser import parse_10027s_markdown

DEFAULT_SOURCE = "10027s"


def _source_config(date, source):
    source = str(source or DEFAULT_SOURCE).lower()
    if source == "10027s":
        return {
            "source": "10027s",
            "source_name": "HH520_10027s",
            "url": build_10027s_url(date, date),
            "parser": parse_10027s_markdown,
        }
    if source == "10023s":
        return {
            "source": "10023s",
            "source_name": "HH520_10023s",
            "url": build_10023s_url(date),
            "parser": parse_10023s_markdown,
        }
    raise ValueError("未知 HH520 数据源")


def validate_raw(date, raw, source=DEFAULT_SOURCE):
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
        raise ValueError(f"响应来源或日期不匹配固定{cfg['source']} URL")
    if metadata.get("statusCode", 200) != 200:
        raise ValueError("页面HTTP状态异常")
    return data["markdown"]


def import_response(date, raw, source=DEFAULT_SOURCE):
    cfg = _source_config(date, source)
    validate_raw(date, raw, source=cfg["source"])
    if load_cache(date, source=cfg["source"]) is not None:
        raise ValueError("该日期和数据源已有缓存，不覆盖")
    payload = {
        "date": date,
        "url": cfg["url"],
        "source": cfg["source_name"],
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "raw": raw,
    }
    try:
        claim_request(date, source=cfg["source"])
    except RuntimeError:
        pass
    save_cache(date, payload, source=cfg["source"])
    return collect_date(date, source=cfg["source"])


def collect_date(date: str, force_refresh: bool = False, source: str = DEFAULT_SOURCE):
    cfg = _source_config(date, source)
    if force_refresh:
        raise ValueError("禁止 force_refresh；同日期同数据源只允许一次抓取")

    payload = load_cache(date, source=cfg["source"])
    if payload is None:
        require_key()
        claim_request(date, source=cfg["source"])
        raw = scrape_markdown(cfg["url"])
        payload = {
            "date": date,
            "url": cfg["url"],
            "source": cfg["source_name"],
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "raw": raw,
        }
        save_cache(date, payload, source=cfg["source"])

    markdown = validate_raw(date, payload.get("raw"), source=cfg["source"])
    payload["matches"] = cfg["parser"](markdown)
    return payload
