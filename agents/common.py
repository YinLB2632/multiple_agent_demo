"""agent 公共小工具：调用大模型、稳健解析 JSON。

大模型有时会把 JSON 包在 ```json``` 里，或前后带解释文字。
这里做容错解析，避免因为模型多说了一句话就整条流水线崩掉。
"""
from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage

from config import build_llm


def call_llm(prompt: str, temperature: float = 0.4) -> str:
    """发一条 prompt，拿回纯文本回复。"""
    llm = build_llm(temperature=temperature)
    resp = llm.invoke([HumanMessage(content=prompt)])
    return resp.content if isinstance(resp.content, str) else str(resp.content)


def parse_json(text: str) -> dict[str, Any]:
    """从模型输出里尽力抠出第一个 JSON 对象。

    解析失败时返回空 dict，由调用方决定降级策略，不抛异常。
    """
    if not text:
        return {}

    # 先去掉 ```json ... ``` 代码围栏
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text

    # 直接尝试
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # 退而求其次：抓第一个 { 到最后一个 } 之间的内容
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(candidate[start : end + 1])
        except json.JSONDecodeError:
            return {}
    return {}


def format_qa(qa_history: list[dict]) -> str:
    """把问答历史拼成可读文本，供提示词填充。"""
    if not qa_history:
        return "（暂无补充问答）"
    return "\n".join(
        f"问：{qa.get('question', '')}\n答：{qa.get('answer', '')}" for qa in qa_history
    )
