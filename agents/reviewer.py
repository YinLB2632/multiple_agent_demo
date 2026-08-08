"""评审专家：给 PRD 打分，不合格给出返修意见。

拆成产品视角 + 技术视角两次独立评审：两边各自打分给意见，
最终分数取二者较低值（有一方不合格就不算合格），意见合并后一起喂给返修。
"""
from __future__ import annotations

from agents.common import call_llm, parse_json
from prompts import PRODUCT_REVIEW_PROMPT, TECH_REVIEW_PROMPT
from state import PRDState


def _parse_review(raw_text: str) -> tuple[int, str]:
    """把一次评审调用的输出稳健解析成 (分数, 意见)。"""
    data = parse_json(raw_text)
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
    return score, feedback


def review_prd(state: PRDState) -> PRDState:
    """从产品视角和技术视角分别评审当前 PRD，合并结果，并把返修计数 +1。"""
    brief = state.get("brief", "")
    prd = state.get("prd", "")

    product_score, product_feedback = _parse_review(
        call_llm(
            PRODUCT_REVIEW_PROMPT.format(brief=brief, prd=prd),
            temperature=0.2,
            role="reviewer",
        )
    )
    tech_score, tech_feedback = _parse_review(
        call_llm(
            TECH_REVIEW_PROMPT.format(brief=brief, prd=prd),
            temperature=0.2,
            role="reviewer",
        )
    )

    # 两边有一方觉得不合格，就不能算合格：取较低分作为最终分数。
    score = min(product_score, tech_score)
    feedback = (
        f"【产品视角】{product_feedback}\n\n【技术视角】{tech_feedback}"
    )

    return {
        "review_score": score,
        "review_feedback": feedback,
        "revision_round": state.get("revision_round", 0) + 1,
        "log": [
            f"🕵️ 评审专家：产品视角 {product_score} 分，技术视角 {tech_score} 分，"
            f"取较低分 {score} 分"
        ],
    }
