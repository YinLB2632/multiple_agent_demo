"""测试 JSON 稳健解析与问答格式化——这是最容易被模型输出搞崩的地方。"""
from agents.common import parse_json, format_qa


def test_parse_plain_json():
    text = '{"enough": true, "questions": []}'
    data = parse_json(text)
    assert data == {"enough": True, "questions": []}


def test_parse_json_in_code_fence():
    text = '这是结果：\n```json\n{"score": 85, "passed": true}\n```\n完毕'
    data = parse_json(text)
    assert data["score"] == 85
    assert data["passed"] is True


def test_parse_json_with_surrounding_text():
    text = '好的，我的判断如下 {"enough": false, "questions": ["给谁用？"]} 以上'
    data = parse_json(text)
    assert data["enough"] is False
    assert data["questions"] == ["给谁用？"]


def test_parse_json_invalid_returns_empty():
    # 彻底不是 JSON 时返回空 dict，不抛异常
    assert parse_json("完全不是json的一段话") == {}
    assert parse_json("") == {}


def test_parse_json_top_level_array_returns_empty():
    # 模型返回合法 JSON 但不是 dict（数组），调用方拿到 {} 而不是列表，
    # 避免 .get() 在列表上 AttributeError
    assert parse_json('[1, 2, 3]') == {}


def test_parse_json_top_level_null_returns_empty():
    # null 也是合法 JSON，但不是 dict
    assert parse_json('null') == {}


def test_parse_json_nested_object():
    # 嵌套对象应当正常解析
    text = '{"a": {"b": 1}, "c": [1, 2]}'
    data = parse_json(text)
    assert data == {"a": {"b": 1}, "c": [1, 2]}


def test_parse_json_braces_in_string_value():
    # 字符串值里有花括号，不应当被当作 JSON 对象边界
    text = '{"msg": "输出 {name}", "ok": true}'
    data = parse_json(text)
    assert data["msg"] == "输出 {name}"
    assert data["ok"] is True


def test_parse_json_multiple_objects_returns_empty():
    # 两个 JSON 对象拼在一起不是合法 JSON，
    # 提取逻辑会把从第一个 { 到最后一个 } 的整段当成候选，解析失败，返回 {}
    text = '{"a": 1} {"b": 2}'
    data = parse_json(text)
    assert data == {}


def test_format_qa_empty():
    out = format_qa([])
    assert out == "（暂无补充问答）"


def test_format_qa_pairs_structure():
    """验证格式而不只是子串——确保问题和答案都按正确顺序出现。"""
    qa = [
        {"question": "给谁用？", "answer": "宠物主人"},
        {"question": "什么平台？", "answer": "微信小程序"},
    ]
    out = format_qa(qa)
    # 内容必须都在
    assert "给谁用？" in out
    assert "宠物主人" in out
    assert "什么平台？" in out
    assert "微信小程序" in out
    # 第一条问题必须先于第二条出现
    assert out.index("给谁用？") < out.index("什么平台？")
    # 每条都包含 问: / 答: 格式
    assert out.count("问：") == 2
    assert out.count("答：") == 2
