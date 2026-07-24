"""AI 产品团队 - 网页界面（Streamlit）。

用法：
    streamlit run app.py

交互流程与 graph.py 一致：输入需求 → 回答澄清问题（关口1）
→ 审阅/编辑/确认需求简报（关口2）→ 看 AI 调研、撰写、评审 → 下载 PRD。
"""
from __future__ import annotations

import streamlit as st
from langgraph.types import Command

from graph import build_graph
from state import initial_state

# 固定线程 id：单用户本地使用，一个会话一条流水线足够
_THREAD_ID = "prd-session"


def _config() -> dict:
    return {"configurable": {"thread_id": _THREAD_ID}}


def _init_session() -> None:
    """初始化会话状态。graph 只建一次，存进 session_state 复用。"""
    if "graph" not in st.session_state:
        st.session_state.graph = build_graph()
    if "phase" not in st.session_state:
        # 阶段机：input → clarify → confirm → done
        st.session_state.phase = "input"
    if "logs" not in st.session_state:
        st.session_state.logs = []
    if "interrupt" not in st.session_state:
        st.session_state.interrupt = None
    if "result" not in st.session_state:
        st.session_state.result = None
    if "error" not in st.session_state:
        st.session_state.error = None


def _drain(stream) -> None:
    """跑一段流水线：累积日志，捕获中断或最终结果。

    LangGraph 的 stream 在 updates 模式下逐节点吐出增量；
    遇到 interrupt 会吐一个特殊的 __interrupt__ 块。
    """
    st.session_state.interrupt = None
    for chunk in stream:
        if not isinstance(chunk, dict):
            continue
        if "__interrupt__" in chunk:
            intr = chunk["__interrupt__"]
            # intr 是 Interrupt 元组，取第一个的 value（我们的 payload）
            st.session_state.interrupt = intr[0].value
            return
        for _node, update in chunk.items():
            if isinstance(update, dict) and update.get("log"):
                st.session_state.logs.extend(update["log"])


def _finalize() -> None:
    """流水线跑完（无中断）时，读取最终状态存起来。"""
    graph = st.session_state.graph
    snapshot = graph.get_state(_config())
    st.session_state.result = snapshot.values
    st.session_state.phase = "done"


def _start_run(requirement: str) -> None:
    """用户提交需求，启动流水线，跑到第一个中断（多半是澄清问题）。"""
    graph = st.session_state.graph
    st.session_state.logs = []
    st.session_state.error = None
    try:
        stream = graph.stream(
            initial_state(requirement), _config(), stream_mode="updates"
        )
        _drain(stream)
    except Exception as exc:  # noqa: BLE001 面向用户兜底，转成友好提示
        st.session_state.error = f"运行出错：{exc}"
        return
    _route_after_drain()


def _resume_run(resume_value) -> None:
    """把用户在关口的输入交回流水线，继续往下跑。"""
    graph = st.session_state.graph
    try:
        stream = graph.stream(
            Command(resume=resume_value), _config(), stream_mode="updates"
        )
        _drain(stream)
    except Exception as exc:  # noqa: BLE001
        st.session_state.error = f"运行出错：{exc}"
        return
    _route_after_drain()


def _route_after_drain() -> None:
    """根据是否命中中断、命中哪种中断，切换界面阶段。"""
    intr = st.session_state.interrupt
    if intr is None:
        _finalize()
        return
    kind = intr.get("type")
    if kind == "clarify":
        st.session_state.phase = "clarify"
    elif kind == "confirm_brief":
        st.session_state.phase = "confirm"


# ============================================================
#  界面主体
# ============================================================

st.set_page_config(page_title="AI 产品团队", page_icon="🧠", layout="wide")
_init_session()

st.title("🧠 AI 产品团队")
st.caption("甩一句模糊需求，AI 团队帮你反问、调研、写出专业 PRD")

# 侧边栏：进度与说明
with st.sidebar:
    st.header("流程")
    st.markdown(
        "1.  需求分析师反问（你回答）\n"
        "2.  审阅确认需求简报（你说了算）\n"
        "3.  市场调研员联网查竞品\n"
        "4.  产品经理写 PRD\n"
        "5.  评审专家把关返修\n"
    )
    st.divider()
    if st.button("🔄 重新开始"):
        for k in ["phase", "logs", "interrupt", "result", "error"]:
            st.session_state.pop(k, None)
        st.rerun()

# 过程日志：实时显示每个 AI 在干活
if st.session_state.logs:
    with st.expander("📜 过程日志", expanded=True):
        for line in st.session_state.logs:
            st.write(line)

# 错误提示
if st.session_state.error:
    st.error(st.session_state.error)

phase = st.session_state.phase

# ---------- 阶段：输入需求 ----------
if phase == "input":
    req = st.text_area(
        "你的需求（一句话就行）",
        placeholder="例如：我想做个帮宠物主人记录疫苗接种时间的 APP",
        height=120,
    )
    if st.button("🚀 交给 AI 团队", type="primary", disabled=not req.strip()):
        with st.spinner("🎯 需求分析师正在读你的需求…"):
            _start_run(req)
        st.rerun()

# ---------- 阶段：澄清问答（关口 1）----------
elif phase == "clarify":
    st.subheader("🎯 需求分析师有几个问题")
    st.caption("回答得越清楚，最终 PRD 越贴合你的想法")
    questions = st.session_state.interrupt.get("questions", [])
    with st.form("clarify_form"):
        answers = [
            st.text_input(f"{i + 1}. {q}", key=f"ans_{i}")
            for i, q in enumerate(questions)
        ]
        if st.form_submit_button("提交回答", type="primary"):
            with st.spinner("🎯 正在消化你的回答…"):
                _resume_run(answers)
            st.rerun()

# ---------- 阶段：审阅确认需求简报（关口 2）----------
elif phase == "confirm":
    st.subheader("📋 需求简报 - 请审阅")
    st.caption("确认无误后才会启动联网调研和撰写。你可以直接在下面修改。")
    brief_text = st.text_area(
        "需求简报（可编辑）",
        value=st.session_state.interrupt.get("brief", ""),
        height=400,
    )
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("✅ 确认，开始生成", type="primary"):
            with st.spinner("🔍 AI 团队开始调研与撰写，这一步较慢，请稍候…"):
                _resume_run({"brief": brief_text})
            st.rerun()
    with col2:
        st.info("提示：这是唯一的确认关口，确认后 AI 会自动完成调研→撰写→评审。")

# ---------- 阶段：完成，展示 PRD ----------
elif phase == "done":
    result = st.session_state.result or {}
    score = result.get("review_score", 0)
    online = result.get("research_online", False)

    c1, c2, c3 = st.columns(3)
    c1.metric("PRD 评审分", f"{score} 分")
    c2.metric("返修轮数", result.get("revision_round", 0))
    c3.metric("联网调研", "是" if online else "否（基于已有知识）")

    tab_prd, tab_research, tab_brief = st.tabs(["📄 PRD", "🔍 市场调研", "📋 需求简报"])
    with tab_prd:
        st.markdown(result.get("prd", "（无内容）"))
        st.download_button(
            "⬇️ 下载 PRD（Markdown）",
            data=result.get("prd", ""),
            file_name="PRD.md",
            mime="text/markdown",
        )
    with tab_research:
        st.markdown(result.get("research", "（无内容）"))
    with tab_brief:
        st.markdown(result.get("brief", "（无内容）"))

