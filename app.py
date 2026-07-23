import json
import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
from src.comparative_matrix import build_comparative_matrix
from src.evaluate import run_ragas_evaluation
from src.generation import generate_answer
from src.indexing import build_index
from src.ingestion import parse_pdf

st.set_page_config(page_title="Academic RAG Studio", page_icon="A", layout="wide")

st.markdown(
    """
    <style>
    :root { color-scheme: dark; }
    .stApp { background: #09111f; }
    [data-testid="stSidebar"] { background: #0e1a2b; border-right: 1px solid #203452; }
    .hero { padding: 2.4rem 0 1.2rem; }
    .eyebrow { color: #5eead4; font-size: .78rem; letter-spacing: .14em; text-transform: uppercase; }
    .hero h1 { color: #f8fafc; font-size: 3rem; line-height: 1.05; margin: .35rem 0 .8rem; }
    .hero p, .muted { color: #9fb0c7; }
    .metric-card { background: #101f33; border: 1px solid #203452; padding: 1.1rem; min-height: 112px; }
    .metric-label { color: #9fb0c7; font-size: .8rem; text-transform: uppercase; letter-spacing: .08em; }
    .metric-value { color: #f8fafc; font-size: 2rem; font-weight: 700; margin-top: .35rem; }
    .feature { border-top: 2px solid #5eead4; padding-top: .7rem; }
    .source-box { border-left: 3px solid #60a5fa; padding-left: .8rem; margin: .5rem 0; }
    </style>
    """,
    unsafe_allow_html=True,
)


def metric_card(label: str, value: str) -> None:
    st.markdown(
        f"<div class='metric-card'><div class='metric-label'>{label}</div>"
        f"<div class='metric-value'>{value}</div></div>",
        unsafe_allow_html=True,
    )


def indexed_stats() -> tuple[int, int]:
    documents = len(list(config.OUTPUT_DIR.glob("*.md")))
    chunks = 0
    docstore_path = config.CHROMADB_DIR / "docstore.json"
    if docstore_path.exists():
        try:
            payload = json.loads(docstore_path.read_text(encoding="utf-8"))
            chunks = len(payload.get("docstore/data", payload.get("nodes", {})))
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    return documents, chunks


def require_login() -> bool:
    if st.session_state.get("authenticated", False):
        return True
    st.warning("Sign in from the Login page to use this workspace.")
    return False


def render_home() -> None:
    documents, chunks = indexed_stats()
    st.markdown(
        "<div class='hero'><div class='eyebrow'>Academic retrieval, made observable</div>"
        "<h1>Research with evidence attached.</h1>"
        "<p>Upload papers, interrogate your corpus, and inspect how retrieval quality changes over time.</p></div>",
        unsafe_allow_html=True,
    )
    cols = st.columns(3)
    for column, label, value in zip(
        cols,
        ["Indexed documents", "Stored chunks", "Confidence gate"],
        [str(documents), str(chunks), f"{config.CONFIDENCE_THRESHOLD:.2f}"],
    ):
        with column:
            metric_card(label, value)

    st.subheader("System architecture")
    st.image(str(config.BASE_DIR / "assets" / "architecture.svg"), use_container_width=True)
    st.divider()
    features = st.columns(3)
    for column, title, body in zip(
        features,
        ["Hierarchical context", "Corrective retrieval", "Measured answers"],
        [
            "Parent-child indexing preserves paper structure while keeping retrieval focused.",
            "Sigmoid-normalized reranking makes the local confidence gate predictable.",
            "Interactive RAGAS charts expose faithfulness, relevance, and precision together.",
        ],
    ):
        with column:
            st.markdown(f"<div class='feature'><h4>{title}</h4><p class='muted'>{body}</p></div>", unsafe_allow_html=True)


def render_login() -> None:
    st.title("Login")
    st.caption("Session-only access for the local workspace.")
    login_tab, signup_tab = st.tabs(["Sign in", "Create account"])
    with login_tab:
        with st.form("auth_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in")
        if submitted:
            if username.strip() and password:
                st.session_state.authenticated = True
                st.session_state.username = username.strip()
                st.success(f"Signed in as {st.session_state.username}.")
                st.rerun()
            else:
                st.error("Enter both a username and password.")
    with signup_tab:
        with st.form("signup_form"):
            new_username = st.text_input("New username")
            new_password = st.text_input("New password", type="password")
            confirm_password = st.text_input("Confirm password", type="password")
            create_account = st.form_submit_button("Create account")
        if create_account:
            if not new_username.strip() or not new_password:
                st.error("Enter a username and password.")
            elif new_password != confirm_password:
                st.error("Passwords do not match.")
            else:
                st.session_state.authenticated = True
                st.session_state.username = new_username.strip()
                st.success(f"Account created for {st.session_state.username}.")
                st.rerun()
    if st.session_state.get("authenticated") and st.button("Sign out"):
        st.session_state.authenticated = False
        st.session_state.pop("username", None)
        st.rerun()


def render_workspace() -> None:
    if not require_login():
        return
    st.title("RAG Workspace")
    mode = st.selectbox("Execution mode", ["local", "cloud"], index=0 if config.config.is_local else 1)
    config.config.set_mode(mode)
    uploaded_files = st.file_uploader("Upload academic PDFs", type=["pdf"], accept_multiple_files=True)
    if uploaded_files and st.button("Process and index PDFs"):
        with st.spinner("Parsing and indexing documents..."):
            for uploaded_file in uploaded_files:
                save_path = config.DATA_DIR / uploaded_file.name
                save_path.write_bytes(uploaded_file.getbuffer())
                parse_pdf(save_path)
            build_index(mode=mode)
        st.success(f"Indexed {len(uploaded_files)} PDF(s).")

    tab_chat, tab_matrix = st.tabs(["Academic chat", "Comparison matrix"])
    with tab_chat:
        if "messages" not in st.session_state:
            st.session_state.messages = []
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        query = st.chat_input("Ask a research question about your indexed papers")
        if query:
            st.session_state.messages.append({"role": "user", "content": query})
            with st.chat_message("user"):
                st.markdown(query)
            with st.chat_message("assistant"):
                started = time.perf_counter()
                with st.spinner("Retrieving evidence and drafting an answer..."):
                    response = generate_answer(query, mode=mode)
                latency = time.perf_counter() - started
                st.markdown(response["answer"])
                gauge = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=response["confidence_score"] * 100,
                    number={"suffix": "%"},
                    title={"text": f"Confidence | {latency:.2f}s"},
                    gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#5eead4"}},
                ))
                gauge.update_layout(height=220, margin={"t": 45, "b": 10, "l": 20, "r": 20}, template="plotly_dark")
                st.plotly_chart(gauge, use_container_width=True)
                with st.expander("Citations"):
                    for source in response["sources"]:
                        st.markdown(
                            f"<div class='source-box'><b>{source.get('filename', source.get('title', 'Source'))}</b></div>",
                            unsafe_allow_html=True,
                        )
            st.session_state.messages.append({"role": "assistant", "content": response["answer"]})
    with tab_matrix:
        if st.button("Generate comparison matrix"):
            with st.spinner("Comparing indexed papers..."):
                matrix = build_comparative_matrix(mode=mode)
            st.dataframe(matrix["dataframe"], use_container_width=True)
            st.download_button("Download Markdown", matrix["markdown_table"], "comparison.md", "text/markdown")


def render_analytics() -> None:
    if not require_login():
        return
    st.title("Analytics")
    st.caption("Run the benchmark to populate the interactive quality profile.")
    if st.button("Run RAGAS benchmark"):
        with st.spinner("Evaluating retrieval and generation..."):
            st.session_state.evaluation = run_ragas_evaluation(mode=config.config.mode)
    evaluation = st.session_state.get("evaluation")
    if evaluation:
        metrics = evaluation["metrics"]
        cols = st.columns(len(metrics))
        for column, (label, value) in zip(cols, metrics.items()):
            with column:
                metric_card(label.replace("_", " "), f"{value:.2f}")
        charts = st.columns(2)
        with charts[0]:
            st.plotly_chart(evaluation["radar_chart"], use_container_width=True)
        with charts[1]:
            st.plotly_chart(evaluation["bar_chart"], use_container_width=True)
        st.dataframe(evaluation["dataframe"], use_container_width=True)


def render_about() -> None:
    st.title("About Academic RAG Studio")
    st.write("A local-first research assistant for exploring academic papers with citations and measurable retrieval quality.")
    st.subheader("Technology stack")
    st.dataframe(pd.DataFrame([
        {"Layer": "Ingestion", "Technology": "LlamaParse and hierarchical parent-child chunks"},
        {"Layer": "Retrieval", "Technology": "ChromaDB, BGE embeddings, BGE reranker base"},
        {"Layer": "Generation", "Technology": "Ollama locally or OpenAI in cloud mode"},
        {"Layer": "Correction", "Technology": "Tavily web fallback through a confidence gate"},
        {"Layer": "Evaluation", "Technology": "RAGAS metrics and Plotly visualizations"},
    ]), use_container_width=True, hide_index=True)


if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

st.sidebar.title("Academic RAG Studio")
page = st.sidebar.radio("Navigate", ["Home", "Login", "RAG Workspace", "Analytics", "About"])
if st.session_state.authenticated:
    st.sidebar.success(f"Signed in: {st.session_state.get('username', 'user')}")
else:
    st.sidebar.info("Guest session")

{"Home": render_home, "Login": render_login, "RAG Workspace": render_workspace, "Analytics": render_analytics, "About": render_about}[page]()
