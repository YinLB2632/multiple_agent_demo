"""配置与模型工厂。

统一在这里读取 .env、创建大模型客户端。
想换模型/搜索源，只改这里和 .env，其它代码不用动。
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


# 各家国产模型的 OpenAI 兼容接入信息：默认模型、接口地址、key 的环境变量名
PROVIDERS: dict[str, dict[str, str]] = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "key_env": "DEEPSEEK_API_KEY",
    },
    "dashscope": {  # 阿里通义千问
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
        "key_env": "DASHSCOPE_API_KEY",
    },
    "zhipu": {  # 智谱 GLM
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
        "key_env": "ZHIPU_API_KEY",
    },
    "moonshot": {  # Kimi
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k",
        "key_env": "MOONSHOT_API_KEY",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "key_env": "OPENAI_API_KEY",
    },
}

# 特殊 provider：用户自接的模型中转站（代理/聚合服务）。
# 与上面固定表不同，它的 base_url / model 也来自环境变量，而非硬编码。
CUSTOM_PROVIDER = "custom"


def read_int_env(name: str, default: int) -> int:
    """读取整数配置，非法值时回退到默认，绝不因配置写错而崩溃。"""
    raw = os.getenv(name, "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """一次性读好所有配置，供全局使用。"""

    llm_provider: str
    llm_model: str
    search_provider: str
    prd_pass_score: int
    max_revision_rounds: int
    max_clarify_rounds: int
    # 仅 custom provider 使用；其他 provider 为空字符串（不存 None，让类型保持干净）
    custom_base_url: str = ""
    custom_api_key: str = ""
    # 评审专家可选的独立模型配置。留空字符串代表"不单独配置，跟其它角色用同一个模型"，
    # 这是刻意选择的默认行为——写手和评审用同一个模型时，写手的判断盲区评审很可能
    # 也判断不出来（自己检查自己的作业）。配了这项，评审就换一家模型来把关。
    reviewer_llm_provider: str = ""
    reviewer_llm_model: str = ""
    reviewer_custom_base_url: str = ""
    reviewer_custom_api_key: str = ""
    # 备用模型：主模型（或评审模型）调用失败（服务挂了/欠费/超时耗尽重试）时，
    # 自动切过去重试一次。留空代表不启用降级，失败就直接抛错——跟改造前行为一致。
    fallback_llm_provider: str = ""
    fallback_llm_model: str = ""
    fallback_custom_base_url: str = ""
    fallback_custom_api_key: str = ""


SUPPORTED_SEARCH_PROVIDERS = {"tavily", "bocha", "none"}


def load_settings() -> Settings:
    """从环境变量装配 Settings（不可变，避免运行中被误改）。

    所有 provider 相关字段都在这里一次性校验，失败立即抛出中文提示，
    不留到实际调用时才报错（fail-fast 原则）。
    """
    provider = os.getenv("LLM_PROVIDER", "deepseek").strip().lower()
    custom_base_url = ""
    custom_api_key = ""

    if provider == CUSTOM_PROVIDER:
        model = os.getenv("LLM_MODEL", "").strip()
        custom_base_url = os.getenv("CUSTOM_BASE_URL", "").strip()
        custom_api_key = os.getenv("CUSTOM_API_KEY", "").strip()
        # 自定义中转站三个字段都是必填，缺任何一个就没法发请求，提前报
        if not model:
            raise ValueError("LLM_PROVIDER=custom 时必须填写 LLM_MODEL（中转站要求的模型名）")
        if not custom_base_url:
            raise ValueError("LLM_PROVIDER=custom 时必须填写 CUSTOM_BASE_URL（中转站接口地址）")
        if not custom_api_key:
            raise ValueError("LLM_PROVIDER=custom 时必须填写 CUSTOM_API_KEY（中转站的 key）")
    elif provider not in PROVIDERS:
        raise ValueError(
            f"不认识的 LLM_PROVIDER：{provider!r}。"
            f"可选：{', '.join(PROVIDERS)}, {CUSTOM_PROVIDER}"
        )
    else:
        model = os.getenv("LLM_MODEL", "").strip() or PROVIDERS[provider]["default_model"]

    search = os.getenv("SEARCH_PROVIDER", "tavily").strip().lower()
    # 搜索 provider 也在这里校验，避免等到真正搜索时才发现配置有误
    if search not in SUPPORTED_SEARCH_PROVIDERS:
        raise ValueError(
            f"不认识的 SEARCH_PROVIDER：{search!r}。"
            f"可选：{', '.join(sorted(SUPPORTED_SEARCH_PROVIDERS))}"
        )

    # 评审专家的独立模型配置，未填写就是空字符串（=跟其它角色共用主模型）
    reviewer_provider = os.getenv("REVIEWER_LLM_PROVIDER", "").strip().lower()
    reviewer_model = ""
    reviewer_custom_base_url = ""
    reviewer_custom_api_key = ""

    if reviewer_provider:
        if reviewer_provider == CUSTOM_PROVIDER:
            reviewer_model = os.getenv("REVIEWER_LLM_MODEL", "").strip()
            reviewer_custom_base_url = os.getenv("REVIEWER_CUSTOM_BASE_URL", "").strip()
            reviewer_custom_api_key = os.getenv("REVIEWER_CUSTOM_API_KEY", "").strip()
            if not reviewer_model:
                raise ValueError(
                    "REVIEWER_LLM_PROVIDER=custom 时必须填写 REVIEWER_LLM_MODEL"
                )
            if not reviewer_custom_base_url:
                raise ValueError(
                    "REVIEWER_LLM_PROVIDER=custom 时必须填写 REVIEWER_CUSTOM_BASE_URL"
                )
            if not reviewer_custom_api_key:
                raise ValueError(
                    "REVIEWER_LLM_PROVIDER=custom 时必须填写 REVIEWER_CUSTOM_API_KEY"
                )
        elif reviewer_provider not in PROVIDERS:
            raise ValueError(
                f"不认识的 REVIEWER_LLM_PROVIDER：{reviewer_provider!r}。"
                f"可选：{', '.join(PROVIDERS)}, {CUSTOM_PROVIDER}"
            )
        else:
            reviewer_model = (
                os.getenv("REVIEWER_LLM_MODEL", "").strip()
                or PROVIDERS[reviewer_provider]["default_model"]
            )

    # 备用模型配置，未填写就是空字符串（=不启用降级，失败直接报错）
    fallback_provider = os.getenv("FALLBACK_LLM_PROVIDER", "").strip().lower()
    fallback_model = ""
    fallback_custom_base_url = ""
    fallback_custom_api_key = ""

    if fallback_provider:
        if fallback_provider == CUSTOM_PROVIDER:
            fallback_model = os.getenv("FALLBACK_LLM_MODEL", "").strip()
            fallback_custom_base_url = os.getenv("FALLBACK_CUSTOM_BASE_URL", "").strip()
            fallback_custom_api_key = os.getenv("FALLBACK_CUSTOM_API_KEY", "").strip()
            if not fallback_model:
                raise ValueError(
                    "FALLBACK_LLM_PROVIDER=custom 时必须填写 FALLBACK_LLM_MODEL"
                )
            if not fallback_custom_base_url:
                raise ValueError(
                    "FALLBACK_LLM_PROVIDER=custom 时必须填写 FALLBACK_CUSTOM_BASE_URL"
                )
            if not fallback_custom_api_key:
                raise ValueError(
                    "FALLBACK_LLM_PROVIDER=custom 时必须填写 FALLBACK_CUSTOM_API_KEY"
                )
        elif fallback_provider not in PROVIDERS:
            raise ValueError(
                f"不认识的 FALLBACK_LLM_PROVIDER：{fallback_provider!r}。"
                f"可选：{', '.join(PROVIDERS)}, {CUSTOM_PROVIDER}"
            )
        else:
            fallback_model = (
                os.getenv("FALLBACK_LLM_MODEL", "").strip()
                or PROVIDERS[fallback_provider]["default_model"]
            )

    return Settings(
        llm_provider=provider,
        llm_model=model,
        search_provider=search,
        prd_pass_score=read_int_env("PRD_PASS_SCORE", 80),
        max_revision_rounds=read_int_env("MAX_REVISION_ROUNDS", 2),
        max_clarify_rounds=read_int_env("MAX_CLARIFY_ROUNDS", 2),
        custom_base_url=custom_base_url,
        custom_api_key=custom_api_key,
        reviewer_llm_provider=reviewer_provider,
        reviewer_llm_model=reviewer_model,
        reviewer_custom_base_url=reviewer_custom_base_url,
        reviewer_custom_api_key=reviewer_custom_api_key,
        fallback_llm_provider=fallback_provider,
        fallback_llm_model=fallback_model,
        fallback_custom_base_url=fallback_custom_base_url,
        fallback_custom_api_key=fallback_custom_api_key,
    )


def _build_client(
    *,
    provider: str,
    model: str,
    custom_base_url: str,
    custom_api_key: str,
    temperature: float,
    who: str,
) -> ChatOpenAI:
    """按 provider 建一个 ChatOpenAI 客户端。三种角色（主/评审/备用）共用这段逻辑，
    避免同样的 if custom / 取 key_env / 缺 key 报错分支复制三份、改一处漏改两处。

    who 只用于报错文案（"评审模型"/"备用模型"/留空代表主模型），不影响行为。
    """
    label = f"{who}" if who else ""
    if provider == CUSTOM_PROVIDER:
        return ChatOpenAI(
            model=model,
            api_key=custom_api_key,
            base_url=custom_base_url,
            temperature=temperature,
            timeout=120,
            max_retries=2,
        )
    conf = PROVIDERS[provider]
    api_key = os.getenv(conf["key_env"], "").strip()
    if not api_key:
        raise ValueError(
            f"没找到{label}{provider} 的 API Key。"
            f"请在 .env 里填写 {conf['key_env']}=你的key"
        )
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=conf["base_url"],
        temperature=temperature,
        timeout=120,
        max_retries=2,
    )


def build_llm(temperature: float = 0.4, role: str = "default") -> ChatOpenAI:
    """按当前配置创建大模型客户端。

    国产模型基本都提供 OpenAI 兼容接口，所以统一用 ChatOpenAI 接入。
    provider=custom 时，base_url / model / key 全部来自用户自填的环境变量，
    用于接入自建或第三方的模型中转站。

    role="reviewer" 且用户配置了 REVIEWER_LLM_PROVIDER 时，走独立的评审模型；
    否则（role="default" 或评审未单独配置）退回主模型——这也是没配时的默认行为，
    跟改造前完全一致，不会因为加了这个开关而影响没配置这项的人。

    直接复用 load_settings() 的解析结果，避免在两处各自重新读环境变量——
    以前两处逻辑分开维护，很容易出现"Settings 里的值和实际建的客户端对不上"。
    """
    settings = load_settings()

    if role == "reviewer" and settings.reviewer_llm_provider:
        return _build_client(
            provider=settings.reviewer_llm_provider,
            model=settings.reviewer_llm_model,
            custom_base_url=settings.reviewer_custom_base_url,
            custom_api_key=settings.reviewer_custom_api_key,
            temperature=temperature,
            who="评审模型 ",
        )

    return _build_client(
        provider=settings.llm_provider,
        model=settings.llm_model,
        custom_base_url=settings.custom_base_url,
        custom_api_key=settings.custom_api_key,
        temperature=temperature,
        who="",
    )


def build_fallback_llm(temperature: float = 0.4) -> ChatOpenAI | None:
    """按配置创建备用模型客户端；未配置 FALLBACK_LLM_PROVIDER 时返回 None。

    调用方（agents/common.call_llm）应在主模型调用耗尽重试仍失败时，
    用这个客户端重试一次；返回 None 就代表没启用降级，维持原来"失败即抛错"的行为。
    """
    settings = load_settings()
    if not settings.fallback_llm_provider:
        return None
    return _build_client(
        provider=settings.fallback_llm_provider,
        model=settings.fallback_llm_model,
        custom_base_url=settings.fallback_custom_base_url,
        custom_api_key=settings.fallback_custom_api_key,
        temperature=temperature,
        who="备用模型 ",
    )
