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
    # parse_json 失败或模型返回非对象 JSON（数组/null 等）时会得到非 dict，统一兜底为空 dict
    if not isinstance(data, dict):
        data = {}

    # 模型可能把 enough 写成字符串 "false"/"no" 等非空垃圾值，bool() 会误判为 True，
    # 这里显式只认 True/"true"/"1"/"yes"（大小写不敏感），其余一律当 False
    enough_raw = data.get("enough", False)
    enough = str(enough_raw).strip().lower() in ("true", "1", "yes")

    raw_questions = data.get("questions", []) or []
    # 模型可能返回 "questions": 3 / true / "一个字符串"（非列表），
    # 直接迭代会崩（int/bool 不可迭代）或产生逐字符的假问题（str 可迭代但不是列表）
    if not isinstance(raw_questions, list):
        raw_questions = []
    # 只保留真正的字符串问题；用 str(q) 硬转会把 dict/list 也变成"看起来像问题"的假文本
    questions = [q.strip() for q in raw_questions if isinstance(q, str) and q.strip()]

    round_no = state.get("clarify_round", 0) + 1
    # 达到最大澄清轮数就强制收尾，避免没完没了地问
    if round_no > settings.max_clarify_rounds:
        enough = True
        questions = []

    # enough=false 但一个问题都没给，属于模型输出异常（不是"信息已足够"），
    # 不能悄悄当作澄清完成——否则会跳过用户本该回答的一轮，且用户毫无察觉
    if not enough and not questions:
        return {
            "clarify_enough": False,
            "pending_questions": [],
            "clarify_round": round_no,
            "log": ["🎯 需求分析师：模型未给出有效问题，本轮跳过（请重试或直接确认简报）"],
        }

    if enough:
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
