"""产品经理：把简报 + 调研写成正规 PRD（支持按评审意见返修）。"""
from __future__ import annotations

from agents.common import call_llm
from prompts import WRITER_PROMPT
from state import PRDState


def write_prd(state: PRDState) -> PRDState:
    """撰写或返修 PRD。带上上一轮评审意见做针对性改进。"""
    feedback = state.get("review_feedback", "").strip()
    round_no = state.get("revision_round", 0)

    prompt = WRITER_PROMPT.format(
        brief=state.get("brief", ""),
        research=state.get("research", ""),
        review_feedback=feedback or "（首次撰写，暂无评审意见）",
    )
    prd = call_llm(prompt, temperature=0.5).strip()

    stage = "首版 PRD 已完成" if round_no == 0 else f"第 {round_no} 轮返修完成"
    return {
        "prd": prd,
        "log": [f"✍️ 产品经理：{stage}"],
    }
