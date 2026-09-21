import os
import time
import requests


class FirecrawlError(RuntimeError):
    pass


_LAST_SCRAPE_AT = 0.0


def require_key():
    key = os.getenv("FIRECRAWL_API_KEY", "").strip()
    if not key or "REPLACE_ME" in key:
        raise FirecrawlError("FIRECRAWL_API_KEY 未配置；在本地 .env 设置，或导入已有 Firecrawl JSON")
    return key


def _pace_scrape_requests():
    """Keep long Research windows from bursting the Firecrawl scrape endpoint."""
    global _LAST_SCRAPE_AT
    min_interval = float(os.getenv("FIRECRAWL_MIN_INTERVAL_SECONDS", "2.5"))
    elapsed = time.monotonic() - _LAST_SCRAPE_AT
    if _LAST_SCRAPE_AT and elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    _LAST_SCRAPE_AT = time.monotonic()


def _retry_after_seconds(response, attempt):
    header = response.headers.get("Retry-After")
    if header:
        try:
            return max(1.0, min(float(header), 90.0))
        except ValueError:
            pass
    backoff = (10.0, 30.0, 60.0, 90.0)
    return backoff[min(attempt, len(backoff) - 1)]


def scrape_markdown(url: str, timeout: int = 60, max_429_retries: int = 4):
    key = require_key()
    payload = {
        "url": url, "formats": ["markdown"], "onlyMainContent": True,
        "proxy": "basic", "storeInCache": True, "maxAge": 0,
    }

    for attempt in range(max_429_retries + 1):
        _pace_scrape_requests()
        try:
            response = requests.post(
                "https://api.firecrawl.dev/v2/scrape",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload, timeout=timeout, allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise FirecrawlError("Firecrawl 请求失败；未自动重试非限流错误") from exc

        if response.status_code == 429:
            if attempt >= max_429_retries:
                raise FirecrawlError(
                    f"Firecrawl HTTP 429；已受控重试 {max_429_retries} 次仍被限流"
                )
            time.sleep(_retry_after_seconds(response, attempt))
            continue

        if response.status_code != 200:
            raise FirecrawlError(f"Firecrawl HTTP {response.status_code}；未自动重试")

        try:
            data = response.json()
        except ValueError as exc:
            raise FirecrawlError("Firecrawl 返回无效 JSON；未自动重试") from exc

        if not isinstance(data, dict) or data.get("success") is not True:
            raise FirecrawlError("Firecrawl 未返回成功结果；未自动重试")
        return data

    raise FirecrawlError("Firecrawl scrape 未完成")


def search_web(query: str, limit: int = 5, timeout: int = 60):
    """Search the public web through Firecrawl v2.

    Research-only callers should cache results and avoid repeated queries.
    """
    key = require_key()
    payload = {"query": query, "limit": max(1, min(int(limit), 10))}
    try:
        response = requests.post(
            "https://api.firecrawl.dev/v2/search",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload, timeout=timeout, allow_redirects=False,
        )
        if response.status_code != 200:
            raise FirecrawlError(f"Firecrawl search HTTP {response.status_code}；未自动重试")
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise FirecrawlError("Firecrawl search 请求失败或返回无效 JSON；未自动重试") from exc
    if not isinstance(data, dict) or data.get("success") is not True:
        raise FirecrawlError("Firecrawl search 未返回成功结果；未自动重试")
    return data
