import os
import requests

class FirecrawlError(RuntimeError):
    pass

def require_key():
    key = os.getenv("FIRECRAWL_API_KEY", "").strip()
    if not key or "REPLACE_ME" in key:
        raise FirecrawlError("FIRECRAWL_API_KEY 未配置；在本地 .env 设置，或导入已有 Firecrawl JSON")
    return key

def scrape_markdown(url: str, timeout: int = 60):
    key = require_key()
    payload = {
        "url": url, "formats": ["markdown"], "onlyMainContent": True,
        "proxy": "basic", "storeInCache": True, "maxAge": 0,
    }
    try:
        response = requests.post(
            "https://api.firecrawl.dev/v2/scrape",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload, timeout=timeout, allow_redirects=False,
        )
        if response.status_code != 200:
            raise FirecrawlError(f"Firecrawl HTTP {response.status_code}；未自动重试")
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise FirecrawlError("Firecrawl 请求失败或返回无效 JSON；未自动重试") from exc
    if not isinstance(data, dict) or data.get("success") is not True:
        raise FirecrawlError("Firecrawl 未返回成功结果；未自动重试")
    return data

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
