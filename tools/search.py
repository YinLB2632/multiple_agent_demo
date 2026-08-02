"""联网搜索模块（可切换 + 优雅降级）。

设计原则：
- 支持 tavily（国外）/ bocha（国产博查）两家，走 REST 接口，只依赖 requests。
- 没配 key 或搜索失败时，绝不让整条流水线崩溃：返回空结果，
  由调研员改用"基于已有知识"模式。外部世界不可信，必须容错。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import requests

# 搜索超时（秒）。设常量，避免魔数散落。
SEARCH_TIMEOUT = 20
# 每个关键词取回的结果条数
MAX_RESULTS = 5


@dataclass
class SearchResult:
    """一次搜索的汇总结果。"""

    online: bool  # 是否真的联网成功
    text: str  # 拼好的可读文本（喂给大模型）
    note: str = ""  # 降级/失败时的说明
    items: list[dict] = field(default_factory=list)  # 原始条目，备查


def tavily_search(query: str, api_key: str) -> list[dict]:
    """调用 Tavily 搜索接口，返回标准化条目列表。"""
    resp = requests.post(
        "https://api.tavily.com/search",
        json={
            "api_key": api_key,
            "query": query,
            "max_results": MAX_RESULTS,
            "search_depth": "basic",
        },
        timeout=SEARCH_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return [
        {
            "title": r.get("title", ""),
            "content": r.get("content", ""),
            "url": r.get("url", ""),
        }
        for r in data.get("results", [])
    ]


def bocha_search(query: str, api_key: str) -> list[dict]:
    """调用博查 AI 搜索接口，返回标准化条目列表。"""
    resp = requests.post(
        "https://api.bochaai.com/v1/web-search",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"query": query, "count": MAX_RESULTS, "summary": True},
        timeout=SEARCH_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    # 博查返回结构：data.webPages.value[]
    pages = (
        data.get("data", {}).get("webPages", {}).get("value", [])
        if isinstance(data.get("data"), dict)
        else []
    )
    return [
        {
            "title": p.get("name", ""),
            "content": p.get("summary") or p.get("snippet", ""),
            "url": p.get("url", ""),
        }
        for p in pages
    ]


def format_items(items: list[dict]) -> str:
    """把搜索条目拼成喂给大模型的可读文本。"""
    lines: list[str] = []
    for i, it in enumerate(items, 1):
        title = it.get("title", "").strip()
        content = it.get("content", "").strip()
        url = it.get("url", "").strip()
        lines.append(f"[{i}] {title}\n{content}\n来源：{url}")
    return "\n\n".join(lines)


def web_search(queries: list[str]) -> SearchResult:
    """按配置执行联网搜索；任何异常都降级为"未联网"，不抛出。

    参数 queries：一组搜索关键词。
    返回 SearchResult：online 标记是否成功联网。
    """
    provider = os.getenv("SEARCH_PROVIDER", "tavily").strip().lower()

    if provider == "none":
        return SearchResult(online=False, text="", note="已配置为不联网（SEARCH_PROVIDER=none）")

    # 未知 provider 必须在推导 key_env 之前就拦截。
    # 如果先推导 key_env，未知 provider 会被当成 bocha 去读 BOCHA_API_KEY；
    # 一旦该 key 没配，会提前返回"未配置 BOCHA_API_KEY"，而不是"不认识的 provider"，
    # 给出误导性诊断。把这个检查前置，让错误信息和真实原因对应。
    if provider not in ("tavily", "bocha"):
        return SearchResult(
            online=False,
            text="",
            note=f"不认识的 SEARCH_PROVIDER：{provider}",
        )

    key_env = "TAVILY_API_KEY" if provider == "tavily" else "BOCHA_API_KEY"
    api_key = os.getenv(key_env, "").strip()
    if not api_key:
        return SearchResult(
            online=False,
            text="",
            note=f"未配置 {key_env}，跳过联网搜索",
        )

    all_items: list[dict] = []
    try:
        for q in queries:
            if not q.strip():
                continue
            if provider == "tavily":
                all_items.extend(tavily_search(q, api_key))
            else:
                all_items.extend(bocha_search(q, api_key))
    except (requests.RequestException, ValueError, KeyError, AttributeError, TypeError) as exc:
        # 网络问题、超时、返回体异常等：一律降级，保证流水线继续跑。
        # AttributeError/TypeError 覆盖搜索提供商返回非 dict body 的情况
        # （如 JSON 数组/null），此时 data.get(...) 会直接抛出。
        return SearchResult(
            online=False,
            text="",
            note=f"联网搜索失败（{type(exc).__name__}），已降级为基于已有知识",
        )

    if not all_items:
        return SearchResult(online=False, text="", note="搜索无结果，降级为基于已有知识")

    return SearchResult(online=True, text=format_items(all_items), items=all_items)
