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


def extract_text(content: Any) -> str:
    """把 LLM 返回的 content 字段规整成纯文本。

    多模态/新版 chat 模型有时不会直接给字符串，而是给一个内容块列表
    （如 [{"type": "text", "text": "..."}]）；content 也可能是 None。
    这里统一拼出可读文本，避免下游把 "None" 或 Python repr 当成正文使用。
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                # block.get("text", "") 遇到 "text": null 仍会返回 None；
                # str(None) 会产生字符串 "None"，用 or "" 彻底堵死这个漏洞
                parts.append(block.get("text") or "")
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content)


def call_llm(prompt: str, temperature: float = 0.4) -> str:
    """发一条 prompt，拿回纯文本回复。"""
    llm = build_llm(temperature=temperature)
    resp = llm.invoke([HumanMessage(content=prompt)])
    return extract_text(resp.content)


def parse_json(text: str) -> dict[str, Any]:
    """从模型输出里尽力抠出第一个 JSON 对象。

    解析失败、或解析出来不是 dict（模型返回了数组/字符串/null 等合法但
    非对象的 JSON）时统一返回空 dict，由调用方决定降级策略，不抛异常。
    """
    if not text:
        return {}

    # 先去掉 ```json ... ``` 代码围栏
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text

    # 直接尝试
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass

    # 退而求其次：抓第一个 { 到最后一个 } 之间的内容
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(candidate[start : end + 1])
            return parsed if isinstance(parsed, dict) else {}
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
