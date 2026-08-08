"""市场调研员：根据确认后的简报，联网查竞品并产出分析。"""
from __future__ import annotations

from agents.common import call_llm, parse_json
from prompts import RESEARCH_PLAN_PROMPT, RESEARCH_GAP_PROMPT, RESEARCH_SUMMARY_PROMPT
from state import PRDState
from tools import web_search
from tools.search import SearchResult, format_items


def research(state: PRDState) -> PRDState:
    """想搜什么 → 联网搜 → 判断够不够具体，不够再补搜一轮 → 揉成调研分析。"""
    brief = state.get("brief", "")
    logs: list[str] = []

    # 1) 让模型想出搜索关键词
    plan = parse_json(call_llm(RESEARCH_PLAN_PROMPT.format(brief=brief), temperature=0.3))
    queries = plan.get("queries", []) or []
    queries = [str(q).strip() for q in queries if str(q).strip()]

    # 2) 第一轮联网搜索（失败自动降级，不会抛异常）
    result = web_search(queries)

    logs.append(
        f"🔍 市场调研员：已联网检索 {len(queries)} 组关键词"
        if result.online
        else f"🔍 市场调研员：{result.note or '未联网'}，改用已有知识"
    )

    # 2.5) 只有第一轮真的联网成功时，才有必要判断"够不够具体"再补搜；
    # 本来就没联网（没配 key / 主动禁用）时，再搜一轮也无济于事，白费一次调用。
    if result.online:
        result = maybe_followup_search(brief, result, logs)

    # 3) 生成调研分析
    summary = call_llm(
        RESEARCH_SUMMARY_PROMPT.format(
            brief=brief,
            search_results=result.text or "（无联网搜索结果）",
        ),
        temperature=0.5,
    ).strip()

    return {
        "research": summary,
        "research_online": result.online,
        "log": logs + ["🔍 市场调研员：竞品与市场分析已完成"],
    }


def maybe_followup_search(brief: str, result: SearchResult, logs: list[str]) -> SearchResult:
    """看一眼第一轮结果，判断是否够具体；不够就补搜最多 2 条关键词并合并结果。

    任何解析/调用异常都不应让整条流水线崩掉——补搜失败时，
    直接沿用第一轮结果即可，不影响主流程。
    """
    gap = parse_json(
        call_llm(
            RESEARCH_GAP_PROMPT.format(brief=brief, search_results=result.text),
            temperature=0.3,
        )
    )
    if not isinstance(gap, dict):
        return result

    enough_raw = gap.get("enough", True)
    enough = str(enough_raw).strip().lower() in ("true", "1", "yes")
    if enough:
        return result

    raw_followups = gap.get("followup_queries", []) or []
    if not isinstance(raw_followups, list):
        raw_followups = []
    followups = [str(q).strip() for q in raw_followups if str(q).strip()][:2]
    if not followups:
        return result

    followup_result = web_search(followups)
    if not followup_result.online or not followup_result.items:
        logs.append("🔍 市场调研员：第一轮结果不够具体，补搜未获得新结果，沿用第一轮")
        return result

    # 合并两轮条目，重新编号，保证引用标注 [n] 与最终文本一一对应
    merged_items = result.items + followup_result.items
    logs.append(f"🔍 市场调研员：第一轮结果不够具体，已补搜 {len(followups)} 条关键词")
    return SearchResult(online=True, text=format_items(merged_items), items=merged_items)
