import os
import time
import requests


class FirecrawlError(RuntimeError):
    pass


_LAST_SCRAPE_AT = 0.0
_FIRECRAWL_RUNTIME = {
    "configured_key_count": 0,
    "request_count": 0,
    "backup_attempted": False,
    "backup_succeeded": False,
    "last_key_index": None,
    "last_status_code": None,
}


def firecrawl_runtime_status():
    """Return safe runtime diagnostics without exposing secret values."""
    out = dict(_FIRECRAWL_RUNTIME)
    out["configured_key_count"] = len(_firecrawl_keys())
    return out


def _firecrawl_keys():
    """Return configured Firecrawl keys in priority order."""
    keys = [
        os.getenv("FIRECRAWL_API_KEY", "").strip(),
        os.getenv("FIRECRAWL_API_KEY_BACKUP", "").strip(),
        os.getenv("FIRECRAWL_API_KEY_BACKUP2", "").strip(),
    ]
    return [k for k in keys if k and "REPLACE_ME" not in k]


def require_key():
    keys = _firecrawl_keys()
    if not keys:
        raise FirecrawlError("FIRECRAWL_API_KEY 未配置；在本地 .env 或 GitHub Secrets 设置")
    return keys[0]


def _pace_scrape_requests():
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


def _post(endpoint: str, payload: dict, timeout: int = 60, *, paced: bool = False):
    if paced:
        _pace_scrape_requests()

    keys = _firecrawl_keys()
    if not keys:
        raise FirecrawlError("Firecrawl API Key 未配置")

    _FIRECRAWL_RUNTIME["configured_key_count"] = len(keys)
    _FIRECRAWL_RUNTIME["request_count"] += 1
    last_error = None
    for index, key in enumerate(keys):
        if index > 0:
            _FIRECRAWL_RUNTIME["backup_attempted"] = True
        try:
            response = requests.post(
                endpoint,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
                timeout=timeout,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            last_error = exc
            continue

        _FIRECRAWL_RUNTIME["last_key_index"] = index
        _FIRECRAWL_RUNTIME["last_status_code"] = response.status_code
        if index > 0 and response.status_code == 200:
            _FIRECRAWL_RUNTIME["backup_succeeded"] = True

        raw_body = response.text if isinstance(response.text, str) else ""
        body = raw_body.lower()
        quota_error = (
            response.status_code in (402, 403)
            or "quota" in body
            or "credits" in body
            or "limit" in body
        )
        if quota_error and index + 1 < len(keys):
            continue

        return response

    if last_error:
        raise FirecrawlError("Firecrawl 请求失败") from last_error
    raise FirecrawlError("Firecrawl 所有账号额度均不可用")


def scrape_markdown(url: str, timeout: int = 60, max_429_retries: int = 4):
    payload = {
        "url": url, "formats": ["markdown"], "onlyMainContent": True,
        "proxy": "basic", "storeInCache": True, "maxAge": 0,
    }

    for attempt in range(max_429_retries + 1):
        response = _post("https://api.firecrawl.dev/v2/scrape", payload, timeout, paced=True)

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


def scrape_json(url: str, schema: dict, prompt: str, timeout: int = 90):
    payload = {
        "url": url,
        "formats": ["json"],
        "jsonOptions": {"schema": schema, "prompt": prompt},
        "onlyMainContent": True,
        "proxy": "basic",
        "storeInCache": True,
        "maxAge": 86400000,
    }
    response = _post("https://api.firecrawl.dev/v2/scrape", payload, timeout, paced=True)
    if response.status_code != 200:
        raise FirecrawlError(f"Firecrawl JSON scrape HTTP {response.status_code}")
    data = response.json()
    if not isinstance(data, dict) or data.get("success") is not True:
        raise FirecrawlError("Firecrawl JSON scrape 未返回成功结果")
    return data


def search_web(query: str, limit: int = 5, timeout: int = 60):
    payload = {"query": query, "limit": max(1, min(int(limit), 10))}
    response = _post("https://api.firecrawl.dev/v2/search", payload, timeout)
    if response.status_code != 200:
        raise FirecrawlError(f"Firecrawl search HTTP {response.status_code}")
    data = response.json()
    if not isinstance(data, dict) or data.get("success") is not True:
        raise FirecrawlError("Firecrawl search 未返回成功结果")
    return data
