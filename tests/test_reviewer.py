"""测试评审专家的双视角评审：产品视角 + 技术视角分别打分，取较低分合并。"""
import json

import agents.reviewer as reviewer_module
from agents.reviewer import review_prd


def _resp(score, passed, feedback):
    return json.dumps({"score": score, "passed": passed, "feedback": feedback})


def test_review_prd_takes_lower_score(monkeypatch):
    """产品视角 90 分、技术视角 60 分时，最终分数必须是 60（较低者），不能是平均或较高者。"""
    calls = []

    def fake_call_llm(prompt, temperature=0.2, role="default"):
        calls.append(prompt)
        if len(calls) == 1:
            return _resp(90, True, "产品逻辑没问题")
        return _resp(60, False, "P0 里塞了工作量很大的功能，优先级不合理")

    monkeypatch.setattr(reviewer_module, "call_llm", fake_call_llm)

    state = {"brief": "简报", "prd": "PRD 内容", "revision_round": 0}
    result = review_prd(state)

    assert result["review_score"] == 60
    assert "【产品视角】产品逻辑没问题" in result["review_feedback"]
    assert "【技术视角】" in result["review_feedback"]
    assert "工作量很大" in result["review_feedback"]
    assert len(calls) == 2  # 两次独立评审调用，不是一次


def test_review_prd_both_pass(monkeypatch):
    def fake_call_llm(prompt, temperature=0.2, role="default"):
        return _resp(85, True, "通过")

    monkeypatch.setattr(reviewer_module, "call_llm", fake_call_llm)

    result = review_prd({"brief": "简报", "prd": "PRD", "revision_round": 1})
    assert result["review_score"] == 85
    assert result["revision_round"] == 2  # 计数器必须 +1


def test_review_prd_handles_malformed_json(monkeypatch):
    """一方返回垃圾输出，不能让整个评审崩掉，应稳健降级为 0 分。"""

    def fake_call_llm(prompt, temperature=0.2, role="default"):
        if "技术负责人" in prompt:
            return "完全不是json"
        return _resp(88, True, "通过")

    monkeypatch.setattr(reviewer_module, "call_llm", fake_call_llm)

    result = review_prd({"brief": "简报", "prd": "PRD", "revision_round": 0})
    # 技术视角解析失败 -> 0 分 -> 取 min(88, 0) = 0
    assert result["review_score"] == 0
