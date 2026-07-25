"""测试配置读取与流水线路由逻辑（纯函数，不烧 API）。"""
import pytest

from config import load_settings, build_llm
from graph import route_after_clarify, route_after_review
from langgraph.graph import END


# ---------- 配置 ----------

def test_load_settings_defaults(monkeypatch):
    for k in ["LLM_PROVIDER", "SEARCH_PROVIDER", "PRD_PASS_SCORE",
              "MAX_REVISION_ROUNDS", "MAX_CLARIFY_ROUNDS", "LLM_MODEL"]:
        monkeypatch.delenv(k, raising=False)
    s = load_settings()
    assert s.llm_provider == "deepseek"
    assert s.prd_pass_score == 80
    assert s.max_revision_rounds == 2


def test_load_settings_bad_int_falls_back(monkeypatch):
    # 配置写错（非数字）时回退默认，不崩
    monkeypatch.setenv("PRD_PASS_SCORE", "不是数字")
    s = load_settings()
    assert s.prd_pass_score == 80


def test_unknown_provider_raises(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "火星模型")
    with pytest.raises(ValueError):
        load_settings()


def test_build_llm_missing_key_raises(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(ValueError) as exc:
        build_llm()
    assert "API Key" in str(exc.value)


# ---------- 自定义模型中转站 ----------

def test_custom_provider_requires_model_for_settings(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "custom")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    with pytest.raises(ValueError) as exc:
        load_settings()
    assert "LLM_MODEL" in str(exc.value)


def test_custom_provider_settings_ok_when_model_set(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "custom")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    s = load_settings()
    assert s.llm_provider == "custom"
    assert s.llm_model == "gpt-4o"


def test_build_llm_custom_missing_base_url_raises(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "custom")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    monkeypatch.setenv("CUSTOM_API_KEY", "sk-xxx")
    monkeypatch.delenv("CUSTOM_BASE_URL", raising=False)
    with pytest.raises(ValueError) as exc:
        build_llm()
    assert "CUSTOM_BASE_URL" in str(exc.value)


def test_build_llm_custom_missing_key_raises(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "custom")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    monkeypatch.setenv("CUSTOM_BASE_URL", "https://proxy.example.com/v1")
    monkeypatch.delenv("CUSTOM_API_KEY", raising=False)
    with pytest.raises(ValueError) as exc:
        build_llm()
    assert "CUSTOM_API_KEY" in str(exc.value)


def test_build_llm_custom_missing_model_raises(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "custom")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setenv("CUSTOM_BASE_URL", "https://proxy.example.com/v1")
    monkeypatch.setenv("CUSTOM_API_KEY", "sk-xxx")
    with pytest.raises(ValueError) as exc:
        build_llm()
    assert "LLM_MODEL" in str(exc.value)


def test_build_llm_custom_builds_client(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "custom")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    monkeypatch.setenv("CUSTOM_BASE_URL", "https://proxy.example.com/v1")
    monkeypatch.setenv("CUSTOM_API_KEY", "sk-xxx")
    llm = build_llm()
    assert llm.model_name == "gpt-4o"
    assert str(llm.openai_api_base) == "https://proxy.example.com/v1"


def test_unknown_provider_error_mentions_custom(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "火星模型")
    with pytest.raises(ValueError) as exc:
        load_settings()
    assert "custom" in str(exc.value)


# ---------- 路由 ----------

def test_route_after_clarify_enough_goes_to_brief():
    state = {"clarify_enough": True, "pending_questions": []}
    assert route_after_clarify(state) == "make_brief"


def test_route_after_clarify_not_enough_asks():
    state = {"clarify_enough": False, "pending_questions": ["给谁用？"]}
    assert route_after_clarify(state) == "collect_answers"


def test_route_after_review_pass_ends(monkeypatch):
    monkeypatch.setenv("PRD_PASS_SCORE", "80")
    state = {"review_score": 85, "revision_round": 1}
    assert route_after_review(state) == END


def test_route_after_review_fail_rewrites(monkeypatch):
    monkeypatch.setenv("PRD_PASS_SCORE", "80")
    monkeypatch.setenv("MAX_REVISION_ROUNDS", "2")
    state = {"review_score": 60, "revision_round": 1}
    assert route_after_review(state) == "write_prd"


def test_route_after_review_max_rounds_ends(monkeypatch):
    # 到返修上限即便不合格也结束，防死循环
    monkeypatch.setenv("PRD_PASS_SCORE", "80")
    monkeypatch.setenv("MAX_REVISION_ROUNDS", "2")
    state = {"review_score": 50, "revision_round": 3}
    assert route_after_review(state) == END
