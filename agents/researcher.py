"""市场调研员：根据确认后的简报，联网查竞品并产出分析。"""
from __future__ import annotations

from agents.common import call_llm, parse_json
from prompts import RESEARCH_PLAN_PROMPT, RESEARCH_SUMMARY_PROMPT
from state import PRDState
from tools import web_search


def research(state: PRDState) -> PRDState:
    """先想搜什么，再联网搜，最后揉成调研分析。"""
    brief = state.get("brief", "")

    # 1) 让模型想出搜索关键词
    plan = parse_json(call_llm(RESEARCH_PLAN_PROMPT.format(brief=brief), temperature=0.3))
    queries = plan.get("queries", []) or []
    queries = [str(q).strip() for q in queries if str(q).strip()]

    # 2) 联网搜索（失败自动降级，不会抛异常）
    result = web_search(queries)

    online_note = (
        f"🔍 市场调研员：已联网检索 {len(queries)} 组关键词"
        if result.online
        else f"🔍 市场调研员：{result.note or '未联网'}，改用已有知识"
    )

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
        "log": [online_note, "🔍 市场调研员：竞品与市场分析已完成"],
    }
