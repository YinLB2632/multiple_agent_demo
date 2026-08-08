"""测试调研员的二次搜索逻辑：第一轮不够具体时补搜，够了就不补搜，没联网就不判断。"""
import json

import agents.researcher as researcher_module
from agents.researcher import research
from tools.search import SearchResult


def _items(n, prefix="item"):
    return [{"title": f"{prefix}{i}", "content": f"内容{i}", "url": f"http://x.com/{i}"} for i in range(n)]


def test_research_skips_gap_check_when_offline(monkeypatch):
    """第一轮就没联网成功（没配 key）时，不该再多打一次模型判断"够不够"，白费调用。"""
    calls = []

    def fake_call_llm(prompt, temperature=0.3):
        calls.append(prompt)
        if "3 条最有价值的搜索关键词" in prompt:
            return json.dumps({"queries": ["a", "b", "c"]})
        return "调研总结内容"

    def fake_web_search(queries):
        return SearchResult(online=False, text="", note="未配置 key")

    monkeypatch.setattr(researcher_module, "call_llm", fake_call_llm)
    monkeypatch.setattr(researcher_module, "web_search", fake_web_search)

    result = research({"brief": "简报"})

    assert result["research_online"] is False
    # 只应该有：生成关键词 1 次 + 生成总结 1 次，没有 gap 判断
    assert len(calls) == 2


def test_research_followup_when_first_round_thin(monkeypatch):
    """第一轮结果空泛时应补搜，且补搜结果要合并进最终搜索文本。"""
    call_log = []

    def fake_call_llm(prompt, temperature=0.3):
        call_log.append(prompt)
        if "3 条最有价值的搜索关键词" in prompt:
            return json.dumps({"queries": ["宠物记账 App"]})
        if "是否已经包含具体的竞品名称" in prompt:
            return json.dumps({"enough": False, "followup_queries": ["某竞品APP 功能"]})
        return "调研总结"

    search_calls = []

    def fake_web_search(queries):
        search_calls.append(list(queries))
        if len(search_calls) == 1:
            return SearchResult(online=True, text="第一轮文本", items=_items(1, "first"))
        return SearchResult(online=True, text="补搜文本", items=_items(1, "second"))

    monkeypatch.setattr(researcher_module, "call_llm", fake_call_llm)
    monkeypatch.setattr(researcher_module, "web_search", fake_web_search)

    result = research({"brief": "简报"})

    assert result["research_online"] is True
    assert len(search_calls) == 2  # 第一轮 + 补搜
    assert any("补搜" in line for line in result["log"])


def test_research_no_followup_when_first_round_enough(monkeypatch):
    """第一轮结果已经够具体时，不应该再补搜第二轮。"""
    search_calls = []

    def fake_call_llm(prompt, temperature=0.3):
        if "3 条最有价值的搜索关键词" in prompt:
            return json.dumps({"queries": ["宠物记账 App"]})
        if "是否已经包含具体的竞品名称" in prompt:
            return json.dumps({"enough": True, "followup_queries": []})
        return "调研总结"

    def fake_web_search(queries):
        search_calls.append(list(queries))
        return SearchResult(online=True, text="第一轮文本", items=_items(1))

    monkeypatch.setattr(researcher_module, "call_llm", fake_call_llm)
    monkeypatch.setattr(researcher_module, "web_search", fake_web_search)

    research({"brief": "简报"})

    assert len(search_calls) == 1  # 不应该有补搜


def test_research_followup_search_fails_falls_back(monkeypatch):
    """补搜本身失败（降级）时，不能让流水线崩，应该沿用第一轮结果。"""

    def fake_call_llm(prompt, temperature=0.3):
        if "3 条最有价值的搜索关键词" in prompt:
            return json.dumps({"queries": ["a"]})
        if "是否已经包含具体的竞品名称" in prompt:
            return json.dumps({"enough": False, "followup_queries": ["b"]})
        return "调研总结"

    search_calls = []

    def fake_web_search(queries):
        search_calls.append(list(queries))
        if len(search_calls) == 1:
            return SearchResult(online=True, text="第一轮文本", items=_items(1))
        return SearchResult(online=False, text="", note="补搜失败")

    monkeypatch.setattr(researcher_module, "call_llm", fake_call_llm)
    monkeypatch.setattr(researcher_module, "web_search", fake_web_search)

    result = research({"brief": "简报"})

    assert result["research_online"] is True  # 沿用第一轮的 online 状态
    assert any("补搜未获得新结果" in line for line in result["log"])
