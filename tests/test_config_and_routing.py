"""测试配置读取与流水线路由逻辑（纯函数，不烧 API）。

注意：所有涉及 load_settings()/build_llm() 的测试都用 monkeypatch 隔离环境变量，
防止开发机的 .env 里残留的值（如 LLM_PROVIDER=custom 缺 LLM_MODEL）导致测试
因"无关原因"失败——测试失败必须只反映被测逻辑本身的问题。
"""
import pytest

from config import load_settings, build_llm
from graph import route_after_clarify, route_after_review
from langgraph.graph import END


# ── 辅助 fixture：把所有 config 相关环境变量清干净，让每个测试从白板出发 ──

ALL_CONFIG_ENVS = [
    "LLM_PROVIDER", "LLM_MODEL", "SEARCH_PROVIDER",
    "PRD_PASS_SCORE", "MAX_REVISION_ROUNDS", "MAX_CLARIFY_ROUNDS",
    "CUSTOM_BASE_URL", "CUSTOM_API_KEY",
    "DEEPSEEK_API_KEY", "DASHSCOPE_API_KEY", "ZHIPU_API_KEY",
    "MOONSHOT_API_KEY", "OPENAI_API_KEY",
]


@pytest.fixture(autouse=True)
def clear_config_env(monkeypatch):
    """每个测试前清空所有 config 相关环境变量，避免开发机环境泄漏进测试。"""
    for k in ALL_CONFIG_ENVS:
        monkeypatch.delenv(k, raising=False)


# ---------- 配置默认值 ----------

def test_load_settings_defaults():
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
    with pytest.raises(ValueError) as exc:
        build_llm()
    assert "API Key" in str(exc.value)


# ---------- 自定义模型中转站 ----------

def test_custom_provider_requires_model(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "custom")
    with pytest.raises(ValueError, match="LLM_MODEL"):
        load_settings()


def test_custom_provider_requires_base_url(monkeypatch):
    # 新增：load_settings 现在也校验 CUSTOM_BASE_URL
    monkeypatch.setenv("LLM_PROVIDER", "custom")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    with pytest.raises(ValueError, match="CUSTOM_BASE_URL"):
        load_settings()


def test_custom_provider_requires_api_key(monkeypatch):
    # 新增：load_settings 现在也校验 CUSTOM_API_KEY
    monkeypatch.setenv("LLM_PROVIDER", "custom")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    monkeypatch.setenv("CUSTOM_BASE_URL", "https://proxy.example.com/v1")
    with pytest.raises(ValueError, match="CUSTOM_API_KEY"):
        load_settings()


def test_custom_provider_settings_ok_when_all_set(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "custom")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    monkeypatch.setenv("CUSTOM_BASE_URL", "https://proxy.example.com/v1")
    monkeypatch.setenv("CUSTOM_API_KEY", "sk-xxx")
    s = load_settings()
    assert s.llm_provider == "custom"
    assert s.llm_model == "gpt-4o"


def test_build_llm_custom_builds_client(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "custom")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    monkeypatch.setenv("CUSTOM_BASE_URL", "https://proxy.example.com/v1")
    monkeypatch.setenv("CUSTOM_API_KEY", "sk-xxx")
    # 不再耦合 ChatOpenAI 的内部属性名（model_name / openai_api_base 可能随版本改变），
    # 只验证对象能成功构造且类型正确。
    from langchain_openai import ChatOpenAI
    llm = build_llm()
    assert isinstance(llm, ChatOpenAI)


def test_unknown_provider_error_mentions_custom(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "火星模型")
    with pytest.raises(ValueError) as exc:
        load_settings()
    assert "custom" in str(exc.value)


def test_unknown_search_provider_raises(monkeypatch):
    # 新增：非法 SEARCH_PROVIDER 应在 load_settings 就报错
    monkeypatch.setenv("SEARCH_PROVIDER", "bing")
    with pytest.raises(ValueError, match="SEARCH_PROVIDER"):
        load_settings()


# ---------- 路由 ----------

def test_route_after_clarify_enough_goes_to_brief():
    state = {"clarify_enough": True, "pending_questions": []}
    assert route_after_clarify(state) == "make_brief"


def test_route_after_clarify_not_enough_asks():
    state = {"clarify_enough": False, "pending_questions": ["给谁用？"]}
    assert route_after_clarify(state) == "collect_answers"


def test_route_after_clarify_abnormal_output_retries():
    # 新增：模型返回 enough=false 但没有问题时（输出异常），
    # 应当重新生成，而不是当作"够了"放过。
    state = {"clarify_enough": False, "pending_questions": []}
    assert route_after_clarify(state) == "clarify_generate"


def test_route_after_review_pass_ends(monkeypatch):
    monkeypatch.setenv("PRD_PASS_SCORE", "80")
    state = {"review_score": 85, "revision_round": 1}
    assert route_after_review(state) == END


def test_route_after_review_score_exactly_80_passes(monkeypatch):
    # 边界值：score 恰好等于 pass_score 应当通过，而非再走一轮返修
    monkeypatch.setenv("PRD_PASS_SCORE", "80")
    monkeypatch.setenv("MAX_REVISION_ROUNDS", "2")
    state = {"review_score": 80, "revision_round": 1}
    assert route_after_review(state) == END


def test_route_after_review_score_79_rewrites(monkeypatch):
    # 边界值对称测试：79 分应当触发返修
    monkeypatch.setenv("PRD_PASS_SCORE", "80")
    monkeypatch.setenv("MAX_REVISION_ROUNDS", "2")
    state = {"review_score": 79, "revision_round": 1}
    assert route_after_review(state) == "write_prd"


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


def test_route_after_review_exactly_at_max_rounds_still_writes(monkeypatch):
    # 边界值：revision_round 恰好等于 max_revision_rounds 时，
    # 实现是 rounds >= max+1，所以 round==2 时应还能再写一次（而非就此结束）
    monkeypatch.setenv("PRD_PASS_SCORE", "80")
    monkeypatch.setenv("MAX_REVISION_ROUNDS", "2")
    state = {"review_score": 50, "revision_round": 2}
    assert route_after_review(state) == "write_prd"
