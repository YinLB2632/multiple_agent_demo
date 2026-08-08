"""各角色的岗位说明书（提示词）。

单独放在这里，方便随时调教某个 AI 的说话风格与产出标准，
不用去翻 agent 代码。
"""
from prompts.clarifier import CLARIFY_QUESTIONS_PROMPT, BRIEF_PROMPT
from prompts.researcher import (
    RESEARCH_PLAN_PROMPT,
    RESEARCH_GAP_PROMPT,
    RESEARCH_SUMMARY_PROMPT,
)
from prompts.writer import WRITER_FEATURES_PROMPT, WRITER_STORIES_PROMPT
from prompts.reviewer import PRODUCT_REVIEW_PROMPT, TECH_REVIEW_PROMPT

__all__ = [
    "CLARIFY_QUESTIONS_PROMPT",
    "BRIEF_PROMPT",
    "RESEARCH_PLAN_PROMPT",
    "RESEARCH_GAP_PROMPT",
    "RESEARCH_SUMMARY_PROMPT",
    "WRITER_FEATURES_PROMPT",
    "WRITER_STORIES_PROMPT",
    "PRODUCT_REVIEW_PROMPT",
    "TECH_REVIEW_PROMPT",
]
