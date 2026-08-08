"""产品经理：把简报 + 调研写成正规 PRD（支持按评审意见返修）。

拆成两步调用大模型：
1) 先写背景/用户场景/功能清单（WRITER_FEATURES_PROMPT）
2) 把第一步结果喂回去，专门展开用户故事/验收标准/其余章节（WRITER_STORIES_PROMPT）
两段拼接成完整 PRD，避免一次性长文本导致后半段被模型敷衍。
"""
from __future__ import annotations

from agents.common import call_llm
from prompts import WRITER_FEATURES_PROMPT, WRITER_STORIES_PROMPT
from state import PRDState


def write_prd(state: PRDState) -> PRDState:
    """撰写或返修 PRD。带上上一轮评审意见做针对性改进。"""

    # 用 or "" 把 None 和空字符串统一归一化。
    feedback = (state.get("review_feedback") or "").strip()
    round_no = state.get("revision_round", 0)
    brief = state.get("brief") or ""

    features_prompt = WRITER_FEATURES_PROMPT.format(
        brief=brief,
        research=state.get("research") or "",
        review_feedback=feedback or "（首次撰写，暂无评审意见）",
    )
    features_section = call_llm(features_prompt, temperature=0.5).strip()

    stories_prompt = WRITER_STORIES_PROMPT.format(
        features_section=features_section,
        brief=brief,
    )
    stories_section = call_llm(stories_prompt, temperature=0.5).strip()

    prd = f"{features_section}\n\n{stories_section}"

    stage = "首版 PRD 已完成" if round_no == 0 else f"第 {round_no} 轮返修完成"
    return {
        "prd": prd,
        "log": [f"✍️ 产品经理：{stage}"],
    }
