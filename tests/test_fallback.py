"""测试 call_llm 的降级逻辑：主模型失败时切到备用模型，没配就原样抛错。"""
import agents.common as common_module
from agents.common import call_llm


class _FakeResp:
    def __init__(self, content):
        self.content = content


class _FakeLLM:
    """invoke() 可配置为抛异常或返回固定内容。"""

    def __init__(self, *, raises=False, content="ok"):
        self.raises = raises
        self.content = content
        self.invoked = False

    def invoke(self, messages):
        self.invoked = True
        if self.raises:
            raise RuntimeError("主模型挂了（模拟服务不可用）")
        return _FakeResp(self.content)


def test_call_llm_uses_fallback_when_primary_fails(monkeypatch):
    """主模型 invoke 抛异常，且配置了备用模型时，应自动切过去重试一次。"""
    primary = _FakeLLM(raises=True)
    fallback = _FakeLLM(content="备用模型的回复")

    monkeypatch.setattr(common_module, "build_llm", lambda temperature, role: primary)
    monkeypatch.setattr(common_module, "build_fallback_llm", lambda temperature: fallback)

    result = call_llm("随便问点什么")

    assert result == "备用模型的回复"
    assert primary.invoked is True
    assert fallback.invoked is True


def test_call_llm_no_fallback_configured_reraises(monkeypatch):
    """主模型失败，但没配置备用模型（build_fallback_llm 返回 None）时，原样抛出异常。"""
    primary = _FakeLLM(raises=True)

    monkeypatch.setattr(common_module, "build_llm", lambda temperature, role: primary)
    monkeypatch.setattr(common_module, "build_fallback_llm", lambda temperature: None)

    try:
        call_llm("随便问点什么")
        assert False, "应当抛出异常，不能被静默吞掉"
    except RuntimeError as exc:
        assert "主模型挂了" in str(exc)


def test_call_llm_primary_success_never_touches_fallback(monkeypatch):
    """主模型正常时，不应该去调用备用模型（哪怕配置了）。"""
    primary = _FakeLLM(content="主模型正常回复")

    def fail_if_called(temperature):
        raise AssertionError("主模型成功时不应该调用 build_fallback_llm")

    monkeypatch.setattr(common_module, "build_llm", lambda temperature, role: primary)
    monkeypatch.setattr(common_module, "build_fallback_llm", fail_if_called)

    result = call_llm("随便问点什么")
    assert result == "主模型正常回复"
