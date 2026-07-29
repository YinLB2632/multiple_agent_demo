"""测试联网搜索的优雅降级——没 key、配置 none 时都不能崩。"""
from tools.search import web_search, SearchResult, format_items


def test_search_none_provider(monkeypatch):
    # 配置为不联网
    monkeypatch.setenv("SEARCH_PROVIDER", "none")
    result = web_search(["宠物记账"])
    assert isinstance(result, SearchResult)
    assert result.online is False
    assert result.text == ""


def test_search_missing_key_degrades(monkeypatch):
    # 选了 tavily 但没配 key，应降级而非报错
    monkeypatch.setenv("SEARCH_PROVIDER", "tavily")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    result = web_search(["宠物记账"])
    assert result.online is False
    assert "TAVILY_API_KEY" in result.note


def test_search_bocha_missing_key_degrades(monkeypatch):
    monkeypatch.setenv("SEARCH_PROVIDER", "bocha")
    monkeypatch.delenv("BOCHA_API_KEY", raising=False)
    result = web_search(["宠物记账"])
    assert result.online is False
    assert "BOCHA_API_KEY" in result.note


def test_format_items():
    items = [{"title": "某APP", "content": "记账工具", "url": "http://x.com"}]
    out = format_items(items)
    assert "某APP" in out
    assert "记账工具" in out
    assert "http://x.com" in out
