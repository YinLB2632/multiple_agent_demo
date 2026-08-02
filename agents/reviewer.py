·"""评审专家：给 PRD 打分，不合格给出返修意见。"""
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
    # parse_json 解析成功但模型返回的是非对象 JSON（数组/null/字符串）时，data 不是 dict，
    # 统一兜底为空 dict，避免下面的 .get 直接抛 AttributeError
    if not isinstance(data, dict):
        data = {}

    # 稳健取值：模型可能给出 "85.5" 这种浮点字符串，直接 int() 会报错。
    # 先转 float 再转 int，只有真正非数字（None/乱码）才落到 except 兜底为 0 分
    try:
        score = int(float(data.get("score", 0)))
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(100, score))  # 夹到 0-100

    # 用 or "" 让 None/空字符串都落到默认提示。
    feedback = str(data.get("feedback") or "").strip() or "（评审未给出具体意见）"

    return {
        "review_score": score,
        "review_feedback": feedback,
        "revision_round": state.get("revision_round", 0) + 1,
        "log": [f"🕵️ 评审专家：本轮打分 {score} 分"],
    }
