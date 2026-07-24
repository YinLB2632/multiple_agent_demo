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
_PROVIDERS: dict[str, dict[str, str]] = {
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


def _int_env(name: str, default: int) -> int:
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


def load_settings() -> Settings:
    """从环境变量装配 Settings（不可变，避免运行中被误改）。"""
    provider = os.getenv("LLM_PROVIDER", "deepseek").strip().lower()
    if provider not in _PROVIDERS:
        raise ValueError(
            f"不认识的 LLM_PROVIDER：{provider!r}。"
            f"可选：{', '.join(_PROVIDERS)}"
        )

    model = os.getenv("LLM_MODEL", "").strip() or _PROVIDERS[provider]["default_model"]
    search = os.getenv("SEARCH_PROVIDER", "tavily").strip().lower()

    return Settings(
        llm_provider=provider,
        llm_model=model,
        search_provider=search,
        prd_pass_score=_int_env("PRD_PASS_SCORE", 80),
        max_revision_rounds=_int_env("MAX_REVISION_ROUNDS", 2),
        max_clarify_rounds=_int_env("MAX_CLARIFY_ROUNDS", 2),
    )


def build_llm(temperature: float = 0.4) -> ChatOpenAI:
    """按当前配置创建大模型客户端。

    国产模型基本都提供 OpenAI 兼容接口，所以统一用 ChatOpenAI 接入。
    缺少 key 时抛出中文提示，而不是让底层库报一堆英文栈。
    """
    provider = os.getenv("LLM_PROVIDER", "deepseek").strip().lower()
    if provider not in _PROVIDERS:
        raise ValueError(
            f"不认识的 LLM_PROVIDER：{provider!r}。可选：{', '.join(_PROVIDERS)}"
        )

    conf = _PROVIDERS[provider]
    api_key = os.getenv(conf["key_env"], "").strip()
    if not api_key:
        raise ValueError(
            f"没找到 {provider} 的 API Key。"
            f"请在 .env 里填写 {conf['key_env']}=你的key"
        )

    model = os.getenv("LLM_MODEL", "").strip() or conf["default_model"]
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=conf["base_url"],
        temperature=temperature,
        timeout=120,
        max_retries=2,
    )
