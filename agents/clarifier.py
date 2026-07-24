"""需求分析师：生成澄清问题 + 整理需求简报。

拆成两个节点函数，配合 graph 里的"暂停问人"使用：
- clarify_generate：判断信息够不够，不够则产出问题（不暂停）
- make_brief：把问答整理成简报（在澄清结束后调用）
"""
from __future__ import annotations

from agents.common import call_llm, parse_json, format_qa
from config import load_settings
from prompts import CLARIFY_QUESTIONS_PROMPT, BRIEF_PROMPT
from state import PRDState


def clarify_generate(state: PRDState) -> PRDState:
    """判断信息是否足够；不够则生成本轮要问的问题。"""
    settings = load_settings()
    qa_text = format_qa(state.get("qa_history", []))

    prompt = CLARIFY_QUESTIONS_PROMPT.format(
        raw_requirement=state["raw_requirement"],
        qa_history=qa_text,
    )
    data = parse_json(call_llm(prompt, temperature=0.3))

    enough = bool(data.get("enough", False))
    questions = data.get("questions", []) or []
    # 只保留字符串问题，防脏数据
    questions = [str(q).strip() for q in questions if str(q).strip()]

    round_no = state.get("clarify_round", 0) + 1
    # 达到最大澄清轮数就强制收尾，避免没完没了地问
    if round_no > settings.max_clarify_rounds:
        enough = True
        questions = []

    if enough or not questions:
        return {
            "clarify_enough": True,
            "pending_questions": [],
            "clarify_round": round_no,
            "log": ["🎯 需求分析师：信息已足够，准备整理需求简报"],
        }

    return {
        "clarify_enough": False,
        "pending_questions": questions,
        "clarify_round": round_no,
        "log": [f"🎯 需求分析师：第 {round_no} 轮，有 {len(questions)} 个问题要问你"],
    }


def make_brief(state: PRDState) -> PRDState:
    """把原始需求 + 全部问答整理成需求简报。"""
    qa_text = format_qa(state.get("qa_history", []))
    prompt = BRIEF_PROMPT.format(
        raw_requirement=state["raw_requirement"],
        qa_history=qa_text,
    )
    brief = call_llm(prompt, temperature=0.4).strip()
    return {
        "brief": brief,
        "log": ["🎯 需求分析师：需求简报已生成，等待你确认"],
    }
