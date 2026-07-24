"""4 个 AI 共享的"工作记忆"。

LangGraph 里每个节点（AI 角色）都读写这一份状态。
用 TypedDict 描述结构，字段含义写在注释里，方便随时回头看。
"""
from __future__ import annotations

import operator
from typing import Annotated

# Python < 3.12 上 pydantic 要求用 typing_extensions 版本的 TypedDict
from typing_extensions import TypedDict


class QAPair(TypedDict):
    """一轮澄清里的一问一答。"""

    question: str
    answer: str


class PRDState(TypedDict, total=False):
    """整条流水线的共享状态。

    total=False 表示字段可以缺省，初始只需给必要项，其余节点逐步填。
    """

    # ---------- 输入 ----------
    raw_requirement: str  # 用户最初甩进来的那句模糊需求

    # ---------- 阶段 1：需求澄清（关口 1）----------
    clarify_round: int  # 已经澄清了几轮，防止无限问
    pending_questions: list[str]  # 本轮要问用户的问题
    qa_history: list[QAPair]  # 历史所有问答
    clarify_enough: bool  # 分析师判断信息是否已足够

    # ---------- 阶段 2：需求简报 + 人工确认（关口 2）----------
    brief: str  # 整理出的结构化需求简报（Markdown）
    brief_confirmed: bool  # 用户是否已确认（未确认绝不进入耗时环节）

    # ---------- 阶段 3：联网调研 ----------
    research: str  # 调研员产出的市场/竞品分析（Markdown）
    research_online: bool  # 是否真的联网了（False=基于已有知识）

    # ---------- 阶段 4：撰写 + 评审返修 ----------
    prd: str  # 当前 PRD 草稿（Markdown）
    review_score: int  # 评审打分 0-100
    review_feedback: str  # 评审意见（返修依据）
    revision_round: int  # 已返修几轮

    # ---------- 过程日志（界面上滚动显示每个 AI 在干活）----------
    # Annotated + operator.add 让各节点追加的日志自动合并，而不是互相覆盖
    log: Annotated[list[str], operator.add]


def initial_state(raw_requirement: str) -> PRDState:
    """根据用户输入构造初始状态，把计数器等都归零。"""
    return {
        "raw_requirement": raw_requirement.strip(),
        "clarify_round": 0,
        "pending_questions": [],
        "qa_history": [],
        "clarify_enough": False,
        "brief": "",
        "brief_confirmed": False,
        "research": "",
        "research_online": False,
        "prd": "",
        "review_score": 0,
        "review_feedback": "",
        "revision_round": 0,
        "log": [],
    }
