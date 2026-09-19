from datetime import datetime, timezone
from .url_builder import build_10023s_url
from .cache_manager import load_cache, save_cache, claim_request
from .firecrawl_client import scrape_markdown, require_key
from .hh520_parser import parse_10023s_markdown

def validate_raw(date, raw):
    url = build_10023s_url(date)
    if not isinstance(raw, dict) or raw.get("success") is not True:
        raise ValueError("需要成功的 Firecrawl 响应 {success:true,data:{markdown,metadata}}")
    data = raw.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("markdown"), str):
        raise ValueError("Firecrawl 缺少 markdown")
    metadata = data.get("metadata") or {}
    source = metadata.get("sourceURL") or metadata.get("url")
    if source != url:
        raise ValueError("响应来源或日期不匹配固定10023s URL")
    title = metadata.get("title", "")
    if title and date not in title:
        raise ValueError("页面标题日期与请求日期不符")
    if metadata.get("statusCode", 200) != 200:
        raise ValueError("页面HTTP状态异常")
    return data["markdown"]

def import_response(date, raw):
    validate_raw(date, raw)
    if load_cache(date) is not None:
        raise ValueError("该日期已有缓存，不覆盖")
    payload = {"date": date, "url": build_10023s_url(date), "source": "HH520_10023s",
               "captured_at": datetime.now(timezone.utc).isoformat(), "raw": raw}
    # Imported responses also reserve the date against future network requests.
    try:
        claim_request(date)
    except RuntimeError:
        pass
    save_cache(date, payload)
    return collect_date(date)

def collect_date(date: str, force_refresh: bool = False):
    url = build_10023s_url(date)
    if force_refresh:
        raise ValueError("Stable 禁止 force_refresh；同日期只允许一次抓取")
    payload = load_cache(date)
    if payload is None:
        require_key()  # Missing key must not consume the one-request ledger.
        claim_request(date)
        raw = scrape_markdown(url)
        payload = {"date": date, "url": url, "source": "HH520_10023s",
                   "captured_at": datetime.now(timezone.utc).isoformat(), "raw": raw}
        # Preserve raw before validation/parsing so parser fixes never refetch.
        save_cache(date, payload)
    markdown = validate_raw(date, payload.get("raw"))
    payload["matches"] = parse_10023s_markdown(markdown)
    # Parsed data stays in memory; saved raw can be re-parsed after a parser update.
    return payload
