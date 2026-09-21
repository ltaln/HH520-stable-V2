import json
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock
import pytest
from collector import cache_manager as cache, service
from collector.url_builder import build_10027s_url
from controller.command_router import parse_command
from collector import firecrawl_client

DATE = "2026-09-19"

@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setenv("FIRECRAWL_API_KEY", "test-key")

def raw():
    return {"success": True, "data": {"markdown": "sample", "metadata": {
        "sourceURL": build_10027s_url(DATE, DATE), "title": DATE, "statusCode": 200}}}

@pytest.mark.parametrize("value", ["2026-02-30", "../a", "2026-1-01", "2026-09-19&x=1"])
def test_bad_dates(value):
    with pytest.raises(ValueError):
        build_10027s_url(value, value)
    with pytest.raises(ValueError):
        parse_command("预测 " + value)

def test_fixed_url():
    assert build_10027s_url(DATE, DATE) == "https://www.hh520.com/tx/10027s.php?riqi_start=2026-09-19&riqi_end=2026-09-19&threshold=1&bankroll=5000"
    with pytest.raises(ValueError):
        build_10027s_url(DATE, DATE, 2)

def test_roundtrip():
    payload = {"date": DATE, "x": "中文"}
    cache.save_cache(DATE, payload)
    assert cache.load_cache(DATE) == payload

def test_corruption_never_fetches(monkeypatch):
    cache.cache_path(DATE).write_text("{", encoding="utf-8")
    scrape = Mock()
    monkeypatch.setattr(service, "scrape_markdown", scrape)
    with pytest.raises(ValueError):
        service.collect_date(DATE)
    scrape.assert_not_called()

def test_cache_first_and_parse_again(monkeypatch):
    scrape = Mock(return_value=raw())
    parser = Mock(return_value=[{"home_team": "A"}])
    monkeypatch.setattr(service, "scrape_markdown", scrape)
    monkeypatch.setattr(service, "parse_10027s_markdown", parser)
    assert service.collect_date(DATE)["matches"] == service.collect_date(DATE)["matches"]
    assert scrape.call_count == 1
    assert parser.call_count == 2

def test_parse_failure_preserves_raw(monkeypatch):
    scrape = Mock(return_value=raw())
    monkeypatch.setattr(service, "scrape_markdown", scrape)
    monkeypatch.setattr(service, "parse_10027s_markdown", Mock(side_effect=ValueError("schema")))
    for _ in range(2):
        with pytest.raises(ValueError):
            service.collect_date(DATE)
    assert scrape.call_count == 1
    assert cache.load_cache(DATE)["raw"] == raw()

def test_network_failure_not_retried(monkeypatch):
    scrape = Mock(side_effect=RuntimeError("timeout"))
    monkeypatch.setattr(service, "scrape_markdown", scrape)
    for _ in range(2):
        with pytest.raises(RuntimeError):
            service.collect_date(DATE)
    assert scrape.call_count == 1

def test_concurrent_reservation():
    def reserve(_):
        try:
            cache.claim_request(DATE)
            return True
        except RuntimeError:
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(reserve, range(8))) == 1

def test_missing_key_does_not_reserve(monkeypatch):
    monkeypatch.delenv("FIRECRAWL_API_KEY")
    with pytest.raises(firecrawl_client.FirecrawlError):
        service.collect_date(DATE)
    assert not cache.cache_path(DATE).with_suffix(".requested").exists()

def test_import_source_check_and_no_refresh():
    response = raw()
    response["data"]["metadata"]["sourceURL"] = "https://example.com"
    with pytest.raises(ValueError):
        service.import_response(DATE, response)
    with pytest.raises(ValueError):
        service.collect_date(DATE, force_refresh=True)

def test_firecrawl_request_contract(monkeypatch):
    response = Mock(status_code=200)
    response.json.return_value = raw()
    post = Mock(return_value=response)
    monkeypatch.setattr(firecrawl_client.requests, "post", post)
    assert firecrawl_client.scrape_markdown(build_10027s_url(DATE, DATE)) == raw()
    args, kwargs = post.call_args
    assert args == ("https://api.firecrawl.dev/v2/scrape",)
    assert kwargs["json"]["proxy"] == "basic"
    assert kwargs["json"]["formats"] == ["markdown"]
    assert kwargs["allow_redirects"] is False
