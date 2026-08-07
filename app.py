"""
規程エージェント Streamlit UI

Layout: left column = chat + trace, right column = source panel
"""
import json
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="規程エージェント",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .main .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }
    .source-card {
        background: #f0f4ff;
        border-left: 4px solid #1a73e8;
        padding: 0.75rem 1rem;
        margin-bottom: 0.75rem;
        border-radius: 0 6px 6px 0;
        font-size: 0.85rem;
    }
    .source-meta {
        color: #5f6368;
        font-size: 0.75rem;
        margin-bottom: 0.35rem;
    }
    .trace-line {
        font-family: monospace;
        font-size: 0.82rem;
        color: #3c4043;
        margin: 2px 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Session state ─────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []  # list of {role, content}
if "last_trace" not in st.session_state:
    st.session_state.last_trace = []
if "last_chunks" not in st.session_state:
    st.session_state.last_chunks = []


def _trace_label(name: str, inp: dict) -> str:
    icon = "🔍" if name == "search_chunks" else "📖"
    if name == "search_chunks":
        arg = inp.get("query", "")
        return f'{icon} search_chunks: "{arg}"'
    if name == "read_section":
        hier = inp.get("hierarchy", "")
        return f'{icon} read_section: "{hier}"'
    return f"{icon} {name}: {json.dumps(inp, ensure_ascii=False)[:60]}"


def _collect_chunks(trace: list) -> list[dict]:
    """Extract all search_chunks results from trace, deduplicated by chunk_id."""
    seen = set()
    chunks = []
    for step in trace:
        for tc in step.get("tool_calls", []):
            if tc["name"] == "search_chunks" and isinstance(tc.get("output"), list):
                for hit in tc["output"]:
                    cid = hit.get("chunk_id", "")
                    if cid not in seen:
                        seen.add(cid)
                        chunks.append(hit)
    return chunks


def run_agent(question: str):
    from src.agent import run as agent_run

    return agent_run(question)


# ── Header ────────────────────────────────────────────────────────────────────
st.title("📋 規程エージェント")
st.caption("公共建築工事標準仕様書（電気設備工事編）令和7年版 — 根拠付き質問応答")

col_chat, col_source = st.columns([3, 2], gap="large")

# ── Right column: source panel ────────────────────────────────────────────────
with col_source:
    st.subheader("📌 根拠パネル")
    source_container = st.container()

    with source_container:
        if st.session_state.last_chunks:
            for chunk in st.session_state.last_chunks:
                hier = chunk.get("hierarchy", "—")
                pages = chunk.get("pages", "—")
                body = chunk.get("body", "")
                heading = chunk.get("heading", "")
                refs = chunk.get("refs", [])

                st.markdown(
                    f'<div class="source-card">'
                    f'<div class="source-meta">📍 {hier} ｜ p.{pages}</div>'
                    f"<strong>{heading}</strong><br>"
                    f"{body[:400]}{'…' if len(body) > 400 else ''}"
                    + (
                        f'<div class="source-meta" style="margin-top:0.4rem;">参照: {", ".join(refs)}</div>'
                        if refs
                        else ""
                    )
                    + "</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.info("質問すると根拠条文がここに表示されます。", icon="ℹ️")

# ── Left column: chat ─────────────────────────────────────────────────────────
with col_chat:
    st.subheader("💬 チャット")

    chat_area = st.container(height=520)

    with chat_area:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    question = st.chat_input("条文について質問してください…")

    if question:
        st.session_state.messages.append({"role": "user", "content": question})

        with chat_area:
            with st.chat_message("user"):
                st.markdown(question)

            with st.chat_message("assistant"):
                with st.status("エージェント実行中…", expanded=True) as status:
                    st.write("⏳ 回答を生成中...")
                    try:
                        result = run_agent(question)
                        trace = result.get("trace", [])
                        answer = result.get("answer", "")
                        chunks = _collect_chunks(trace)

                        for step in trace:
                            for tc in step.get("tool_calls", []):
                                st.write(_trace_label(tc["name"], tc["input"]))

                        status.update(
                            label=f"完了（{sum(len(s['tool_calls']) for s in trace)} ツール呼び出し）",
                            state="complete",
                            expanded=False,
                        )

                        st.session_state.last_trace = trace
                        st.session_state.last_chunks = chunks

                    except Exception as exc:
                        status.update(label="エラー", state="error")
                        answer = f"⚠️ エラーが発生しました: {exc}"

                st.markdown(answer)

        st.session_state.messages.append({"role": "assistant", "content": answer})
        st.rerun()
