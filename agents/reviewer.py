"""评审专家：给 PRD 打分，不合格给出返修意见。"""
from __future__ import annotations

from agents.common import call_llm, parse_json
from prompts import REVIEWER_PROMPT
from state import PRDState


def review_prd(state: PRDState) -> PRDState:
    """评审当前 PRD，产出分数与意见，并把返修计数 +1。"""
    prompt = REVIEWER_PROMPT.format(
        brief=state.get("brief", ""),
        prd=state.get("prd", ""),
    )
    data = parse_json(call_llm(prompt, temperature=0.2))

    # 稳健取值：模型可能给出非整数或缺字段
    try:
        score = int(data.get("score", 0))
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(100, score))  # 夹到 0-100

    feedback = str(data.get("feedback", "")).strip() or "（评审未给出具体意见）"

    return {
        "review_score": score,
        "review_feedback": feedback,
        "revision_round": state.get("revision_round", 0) + 1,
        "log": [f"🕵️ 评审专家：本轮打分 {score} 分"],
    }
