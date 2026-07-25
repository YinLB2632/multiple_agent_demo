"""把 4 个 AI 角色串成一条流水线（LangGraph）。

流程（两个"你说了算"的关口）：

  START
    │
    ▼
  clarify_generate ──不够──► collect_answers【关口1：回答问题】
    │  ▲                              │
    │  └───────────回答后回到判断───────┘
    │
    ▼ 够了
  make_brief   整理需求简报
    │
    ▼
  confirm_brief【关口2：人工审阅/编辑/确认，确认后才进入耗时环节】
    │
    ▼
  do_research  联网调研
    │
    ▼
  write_prd ◄──────────────┐  撰写 / 按评审意见返修 PRD
    │                      │
    ▼                      │
  review_prd  评审打分      │
    │                      │
    └──不合格且没超返修上限──┘
    │
    ▼ 合格或到返修上限
  END

注意：collect_answers 只会跳回 clarify_generate 重新判断信息是否够，
不会流向 confirm_brief——两个关口分别把守两段不同的循环，互不相通。
"""
from __future__ import annotations

from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt

from agents.clarifier import clarify_generate, make_brief
from agents.researcher import research
from agents.writer import write_prd
from agents.reviewer import review_prd
from config import load_settings
from state import PRDState, QAPair


# ---------- 两个人工关口对应的节点 ----------

def collect_answers(state: PRDState) -> PRDState:
    """关口 1：暂停，把问题抛给用户，收到回答后合并进问答历史。

    interrupt() 会让整张图停在这里；界面拿到 payload 显示问题，
    用户回答后通过 Command(resume=答案列表) 恢复执行。
    """
    payload = {"type": "clarify", "questions": state.get("pending_questions", [])}
    answers = interrupt(payload)  # 恢复后，answers 就是用户提交的答案列表

    questions = state.get("pending_questions", [])
    answers = answers or []
    new_qa: list[QAPair] = [
        {"question": q, "answer": str(answers[i]) if i < len(answers) else "（未回答）"}
        for i, q in enumerate(questions)
    ]
    merged = state.get("qa_history", []) + new_qa
    return {
        "qa_history": merged,
        "pending_questions": [],
        "log": [f"🙋 你回答了 {len(new_qa)} 个问题"],
    }


def confirm_brief(state: PRDState) -> PRDState:
    """关口 2：暂停，把需求简报交给用户审阅/编辑/确认。

    确认前绝不进入后面又慢又费钱的调研与撰写环节。
    resume 传回 {"brief": 最终文本}，用户的编辑即最终版。
    """
    decision = interrupt({"type": "confirm_brief", "brief": state.get("brief", "")})
    decision = decision or {}
    final_brief = (decision.get("brief") or state.get("brief", "")).strip()
    return {
        "brief": final_brief,
        "brief_confirmed": True,
        "log": ["📋 你已确认需求简报，开始联网调研"],
    }


# ---------- 条件路由 ----------

def route_after_clarify(state: PRDState) -> Literal["collect_answers", "make_brief"]:
    """信息够了去整理简报，不够就去问用户。"""
    if state.get("clarify_enough") or not state.get("pending_questions"):
        return "make_brief"
    return "collect_answers"


def route_after_review(state: PRDState) -> Literal["write_prd", END]:
    """合格或到返修上限就结束，否则打回重写。"""
    settings = load_settings()
    score = state.get("review_score", 0)
    rounds = state.get("revision_round", 0)
    if score >= settings.prd_pass_score or rounds >= settings.max_revision_rounds + 1:
        return END
    return "write_prd"


def build_graph():
    """组装并编译流水线。带 MemorySaver 以支持"暂停-恢复"。"""
    g = StateGraph(PRDState)

    # 注册节点
    g.add_node("clarify_generate", clarify_generate)
    g.add_node("collect_answers", collect_answers)
    g.add_node("make_brief", make_brief)
    g.add_node("confirm_brief", confirm_brief)
    g.add_node("do_research", research)  # 节点名不能与状态字段 research 重名
    g.add_node("write_prd", write_prd)
    g.add_node("review_prd", review_prd)

    # 连边
    g.add_edge(START, "clarify_generate")
    g.add_conditional_edges(
        "clarify_generate",
        route_after_clarify,
        ["collect_answers", "make_brief"],
    )
    g.add_edge("collect_answers", "clarify_generate")  # 回答后再判断是否够
    g.add_edge("make_brief", "confirm_brief")
    g.add_edge("confirm_brief", "do_research")  # 关口 2 通过后进入耗时环节
    g.add_edge("do_research", "write_prd")
    g.add_edge("write_prd", "review_prd")
    g.add_conditional_edges(
        "review_prd",
        route_after_review,
        ["write_prd", END],
    )

    return g.compile(checkpointer=MemorySaver())
