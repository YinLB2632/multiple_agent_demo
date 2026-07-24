"""测试 JSON 稳健解析与问答格式化——这是最容易被模型输出搞崩的地方。"""
from agents.common import parse_json, format_qa


def test_parse_plain_json():
    # Arrange
    text = '{"enough": true, "questions": []}'
    # Act
    data = parse_json(text)
    # Assert
    assert data == {"enough": True, "questions": []}


def test_parse_json_in_code_fence():
    # 模型爱把 JSON 包在 ```json ``` 里
    text = '这是结果：\n```json\n{"score": 85, "passed": true}\n```\n完毕'
    data = parse_json(text)
    assert data["score"] == 85
    assert data["passed"] is True


def test_parse_json_with_surrounding_text():
    # 前后带解释文字也要能抠出来
    text = '好的，我的判断如下 {"enough": false, "questions": ["给谁用？"]} 以上'
    data = parse_json(text)
    assert data["enough"] is False
    assert data["questions"] == ["给谁用？"]


def test_parse_json_invalid_returns_empty():
    # 彻底不是 JSON 时返回空 dict，不抛异常
    assert parse_json("完全不是json的一段话") == {}
    assert parse_json("") == {}


def test_format_qa_empty():
    assert "暂无" in format_qa([])


def test_format_qa_pairs():
    qa = [{"question": "给谁用？", "answer": "宠物主人"}]
    out = format_qa(qa)
    assert "给谁用？" in out
    assert "宠物主人" in out
