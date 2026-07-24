"""测试初始状态构造——保证计数器归零、字段齐全。"""
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


def test_initial_state_has_all_keys():
    s = initial_state("x")
    expected = {
        "raw_requirement", "clarify_round", "pending_questions", "qa_history",
        "clarify_enough", "brief", "brief_confirmed", "research",
        "research_online", "prd", "review_score", "review_feedback",
        "revision_round", "log",
    }
    assert expected.issubset(s.keys())
