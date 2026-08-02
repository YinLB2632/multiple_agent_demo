"""测试初始状态构造——保证计数器归零、字段齐全。"""
import pytest
from state import initial_state


def test_initial_state_strips_and_zeros():
    # Arrange & Act
    s = initial_state("  做个记账APP  ")
    # Assert
    assert s["raw_requirement"] == "做个记账APP"  # 去掉首尾空格
    assert s["clarify_round"] == 0
    assert s["revision_round"] == 0
    assert s["brief_confirmed"] is False
    assert s["qa_history"] == []
    assert s["log"] == []


def test_initial_state_has_exactly_all_keys():
    """精确匹配 schema，多一个或少一个字段都应该失败。

    原来用 issubset 只能发现"缺字段"，新字段悄悄加进来却永远发现不了，
    改成精确相等让 schema 漂移一出现测试就红。
    """
    s = initial_state("x")
    expected = {
        "raw_requirement", "clarify_round", "pending_questions", "qa_history",
        "clarify_enough", "brief", "brief_confirmed", "research",
        "research_online", "prd", "review_score", "review_feedback",
        "revision_round", "log",
    }
    assert set(s.keys()) == expected


def test_initial_state_empty_requirement_raises():
    """空白需求应该在入口处快速失败，而不是默默传进流水线产出垃圾。"""
    with pytest.raises(ValueError, match="不能为空"):
        initial_state("   ")


def test_initial_state_purely_whitespace_raises():
    with pytest.raises(ValueError):
        initial_state("\t\n")
