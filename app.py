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
from src.user_store import (
    create_user,
    user_exists,
    validate_password,
    validate_username,
    verify_user,
)

# --------------------------------------------------------------------------
# Page configuration
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="Academic RAG Studio",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

PAGES = [
    ("Home", "🏠"),
    ("RAG Workspace", "💬"),
    ("Analytics", "📊"),
    ("About", "ℹ️"),
]

# --------------------------------------------------------------------------
# Global theme
# --------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    :root {
        color-scheme: dark;
        --bg: #0a0f1a;
        --bg-elevated: #0f1826;
        --surface: #121e30;
        --surface-hover: #16263c;
        --border: #223350;
        --border-soft: #1a2942;
        --text-primary: #f1f5f9;
        --text-secondary: #94a7c4;
        --text-muted: #6b7f9e;
        --accent: #2dd4bf;
        --accent-strong: #14b8a6;
        --accent-soft: rgba(45, 212, 191, 0.12);
        --blue: #60a5fa;
        --danger: #f87171;
        --radius: 14px;
    }

    html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }
    .stApp { background: radial-gradient(circle at 10% 0%, #0e1b30 0%, var(--bg) 45%); }

    /* ---- Sidebar ---- */
    [data-testid="stSidebar"] {
        background: var(--bg-elevated);
        border-right: 1px solid var(--border-soft);
    }
    [data-testid="stSidebar"] .block-container { padding-top: 1.4rem; }

    .brand {
        display: flex; align-items: center; gap: .6rem;
        padding: 0 .1rem 1.1rem 0;
        border-bottom: 1px solid var(--border-soft);
        margin-bottom: 1.1rem;
    }
    .brand-mark {
        width: 38px; height: 38px; border-radius: 10px;
        background: linear-gradient(135deg, var(--accent) 0%, #0891b2 100%);
        display: flex; align-items: center; justify-content: center;
        font-size: 1.1rem; font-weight: 800; color: #04211c; flex-shrink: 0;
    }
    .brand-name { color: var(--text-primary); font-weight: 700; font-size: 1.02rem; line-height: 1.15; }
    .brand-sub { color: var(--text-muted); font-size: .72rem; letter-spacing: .04em; }

    .session-card {
        background: var(--surface); border: 1px solid var(--border-soft);
        border-radius: var(--radius); padding: .85rem .95rem; margin-top: 1.2rem;
    }
    .session-row { display: flex; align-items: center; gap: .6rem; }
    .avatar {
        width: 34px; height: 34px; border-radius: 50%; flex-shrink: 0;
        background: var(--accent-soft); color: var(--accent);
        display: flex; align-items: center; justify-content: center;
        font-weight: 700; font-size: .85rem; border: 1px solid rgba(45,212,191,.35);
    }
    .session-name { color: var(--text-primary); font-weight: 600; font-size: .88rem; }
    .session-status { color: var(--text-muted); font-size: .74rem; }
    .status-dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: var(--accent); margin-right: 5px; }
    .status-dot.off { background: var(--text-muted); }

    [data-testid="stSidebar"] .stRadio > label { display: none; }
    [data-testid="stSidebar"] .stRadio [role="radiogroup"] { gap: .25rem; }
    [data-testid="stSidebar"] .stRadio [role="radiogroup"] label {
        background: transparent; border-radius: 10px; padding: .5rem .7rem;
        transition: background .15s ease; width: 100%;
    }
    [data-testid="stSidebar"] .stRadio [role="radiogroup"] label:hover { background: var(--surface-hover); }
    [data-testid="stSidebar"] .stRadio [role="radiogroup"] label p { color: var(--text-secondary) !important; font-weight: 500; font-size: .92rem; }

    /* ---- Layout helpers ---- */
    .block-container { padding-top: 2.4rem; max-width: 1180px; }

    .page-header { margin-bottom: 1.6rem; }
    .eyebrow {
        color: var(--accent); font-size: .74rem; font-weight: 700;
        letter-spacing: .16em; text-transform: uppercase;
    }
    .page-title { color: var(--text-primary); font-size: 2.1rem; font-weight: 800; margin: .3rem 0 .35rem; letter-spacing: -.01em; }
    .page-subtitle { color: var(--text-secondary); font-size: 1rem; max-width: 640px; line-height: 1.55; }

    .hero {
        background: linear-gradient(155deg, var(--surface) 0%, var(--bg-elevated) 100%);
        border: 1px solid var(--border-soft); border-radius: 20px;
        padding: 2.6rem 2.8rem; margin-bottom: 1.8rem;
    }
    .hero h1 { color: var(--text-primary); font-size: 2.6rem; line-height: 1.1; margin: .5rem 0 .9rem; font-weight: 800; letter-spacing: -.02em; }
    .hero p { color: var(--text-secondary); font-size: 1.05rem; max-width: 620px; line-height: 1.6; }

    /* ---- Cards ---- */
    .metric-card {
        background: var(--surface); border: 1px solid var(--border-soft);
        border-radius: var(--radius); padding: 1.25rem 1.3rem; min-height: 108px;
        transition: border-color .15s ease;
    }
    .metric-card:hover { border-color: var(--border); }
    .metric-label { color: var(--text-muted); font-size: .76rem; text-transform: uppercase; letter-spacing: .08em; font-weight: 600; }
    .metric-value { color: var(--text-primary); font-size: 1.9rem; font-weight: 800; margin-top: .4rem; letter-spacing: -.01em; }

    .feature-card {
        background: var(--surface); border: 1px solid var(--border-soft);
        border-radius: var(--radius); padding: 1.4rem 1.4rem 1.5rem; height: 100%;
    }
    .feature-icon {
        width: 36px; height: 36px; border-radius: 9px; background: var(--accent-soft);
        display: flex; align-items: center; justify-content: center; font-size: 1.05rem; margin-bottom: .8rem;
    }
    .feature-card h4 { color: var(--text-primary); font-size: 1.02rem; font-weight: 700; margin: 0 0 .4rem; }
    .feature-card p { color: var(--text-secondary); font-size: .9rem; line-height: 1.55; margin: 0; }

    .source-box {
        border-left: 3px solid var(--blue); background: var(--surface);
        border-radius: 0 10px 10px 0; padding: .6rem .9rem; margin: .5rem 0;
    }
    .source-title { color: var(--text-primary); font-weight: 600; font-size: .88rem; }
    .source-meta { color: var(--text-muted); font-size: .76rem; margin-top: .15rem; }

    section[data-testid="stTabs"] button[role="tab"] p { font-weight: 600; }

    /* ---- Login ---- */
    .auth-wrap { display: flex; justify-content: center; padding-top: 1.2rem; }
    .auth-card {
        width: 100%; max-width: 420px; background: var(--surface);
        border: 1px solid var(--border-soft); border-radius: 18px;
        padding: 2.2rem 2.2rem 1.6rem;
    }
    .auth-mark {
        width: 46px; height: 46px; border-radius: 12px; margin: 0 auto .9rem;
        background: linear-gradient(135deg, var(--accent) 0%, #0891b2 100%);
        display: flex; align-items: center; justify-content: center;
        font-size: 1.3rem; font-weight: 800; color: #04211c;
    }
    .auth-title { color: var(--text-primary); font-size: 1.35rem; font-weight: 800; text-align: center; margin: 0 0 .25rem; }
    .auth-subtitle { color: var(--text-muted); font-size: .86rem; text-align: center; margin-bottom: 1.5rem; }
    .auth-footnote { color: var(--text-muted); font-size: .78rem; text-align: center; margin-top: 1rem; }

    .stTextInput input, .stSelectbox [data-baseweb="select"] > div {
        background: var(--bg-elevated) !important; border: 1px solid var(--border) !important;
        border-radius: 9px !important; color: var(--text-primary) !important;
    }
    .stTextInput input:focus { border-color: var(--accent) !important; box-shadow: 0 0 0 1px var(--accent) !important; }
    .stTextInput label, .stSelectbox label, .stFileUploader label { color: var(--text-secondary) !important; font-weight: 500; font-size: .88rem; }

    .stButton > button, .stFormSubmitButton > button {
        background: var(--accent); color: #04211c; border: none; border-radius: 9px;
        font-weight: 700; padding: .5rem 1.1rem; transition: background .15s ease;
    }
    .stButton > button:hover, .stFormSubmitButton > button:hover { background: var(--accent-strong); color: #04211c; }
    .stButton > button[kind="secondary"] { background: transparent; border: 1px solid var(--border); color: var(--text-secondary); }

    .stAlert { border-radius: 10px; }
    hr { border-color: var(--border-soft); }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------
def page_header(eyebrow: str, title: str, subtitle: str) -> None:
    st.markdown(
        f"<div class='page-header'><div class='eyebrow'>{eyebrow}</div>"
        f"<div class='page-title'>{title}</div>"
        f"<div class='page-subtitle'>{subtitle}</div></div>",
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
    st.warning("Please sign in to use this workspace.", icon="🔒")
    if st.button("Go to sign in"):
        st.session_state.nav_page = "Login"
        st.rerun()
    return False


def initials(name: str) -> str:
    parts = [p for p in name.strip().split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------
def render_home() -> None:
    documents, chunks = indexed_stats()
    st.markdown(
        "<div class='hero'><div class='eyebrow'>Academic retrieval, made observable</div>"
        "<h1>Research with evidence attached.</h1>"
        "<p>Upload papers, interrogate your corpus, and inspect how retrieval quality "
        "changes over time — every answer comes with the sources behind it.</p></div>",
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

    st.write("")
    st.subheader("System architecture")
    st.image(str(config.BASE_DIR / "assets" / "architecture.svg"), use_container_width=True)

    st.write("")
    st.subheader("Why it's built this way")
    features = st.columns(3)
    feature_data = [
        ("🧩", "Hierarchical context", "Parent-child indexing preserves paper structure while keeping retrieval focused."),
        ("🎯", "Corrective retrieval", "Sigmoid-normalized reranking makes the local confidence gate predictable."),
        ("📈", "Measured answers", "Interactive RAGAS charts expose faithfulness, relevance, and precision together."),
    ]
    for column, (icon, title, body) in zip(features, feature_data):
        with column:
            st.markdown(
                f"<div class='feature-card'><div class='feature-icon'>{icon}</div>"
                f"<h4>{title}</h4><p>{body}</p></div>",
                unsafe_allow_html=True,
            )

    if not st.session_state.get("authenticated"):
        st.write("")
        st.info("Sign in to upload papers, ask questions, and run evaluations.", icon="👋")


def render_login() -> None:
    st.markdown("<div class='auth-wrap'>", unsafe_allow_html=True)
    _, center, _ = st.columns([1, 1.3, 1])
    with center:
        st.markdown(
            "<div class='auth-card'>"
            "<div class='auth-mark'>A</div>"
            "<div class='auth-title'>Welcome back</div>"
            "<div class='auth-subtitle'>Sign in to access your research workspace.</div>",
            unsafe_allow_html=True,
        )

        if st.session_state.get("authenticated"):
            st.success(f"Signed in as **{st.session_state.get('display_name', 'user')}**.", icon="✅")
            if st.button("Sign out", use_container_width=True):
                st.session_state.authenticated = False
                st.session_state.pop("username", None)
                st.session_state.pop("display_name", None)
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            return

        login_tab, signup_tab = st.tabs(["Sign in", "Create account"])

        with login_tab:
            with st.form("auth_form", border=False):
                username = st.text_input("Username", placeholder="jane.doe")
                password = st.text_input("Password", type="password", placeholder="••••••••")
                submitted = st.form_submit_button("Sign in", use_container_width=True)
            if submitted:
                if not username.strip() or not password:
                    st.error("Enter both a username and password.")
                else:
                    record = verify_user(username.strip(), password)
                    if record:
                        st.session_state.authenticated = True
                        st.session_state.username = record["username"]
                        st.session_state.display_name = record["display_name"]
                        st.success(f"Signed in as {record['display_name']}.")
                        st.rerun()
                    else:
                        st.error("Incorrect username or password.")

        with signup_tab:
            with st.form("signup_form", border=False):
                new_username = st.text_input("Username", placeholder="Choose a unique username", key="su_user")
                new_password = st.text_input("Password", type="password", placeholder="At least 8 characters", key="su_pass")
                confirm_password = st.text_input("Confirm password", type="password", key="su_confirm")
                create_account = st.form_submit_button("Create account", use_container_width=True)
            if create_account:
                username_error = validate_username(new_username.strip())
                password_error = validate_password(new_password)
                if username_error:
                    st.error(username_error)
                elif user_exists(new_username.strip()):
                    st.error("That username is already taken.")
                elif password_error:
                    st.error(password_error)
                elif new_password != confirm_password:
                    st.error("Passwords do not match.")
                else:
                    create_user(new_username.strip(), new_password)
                    st.session_state.authenticated = True
                    st.session_state.username = new_username.strip()
                    st.session_state.display_name = new_username.strip()
                    st.success("Account created. You're signed in.")
                    st.rerun()

        st.markdown(
            "<div class='auth-footnote'>Accounts are stored locally for this workspace instance.</div>",
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def render_workspace() -> None:
    page_header("Workspace", "RAG Workspace", "Upload academic PDFs, ask grounded questions, and compare papers side by side.")
    if not require_login():
        return

    with st.container(border=True):
        top = st.columns([2, 1])
        with top[0]:
            st.markdown("**Upload & index**")
            uploaded_files = st.file_uploader(
                "Upload academic PDFs", type=["pdf"], accept_multiple_files=True, label_visibility="collapsed"
            )
        with top[1]:
            st.markdown("**Execution mode**")
            mode = st.selectbox(
                "Execution mode",
                ["local", "cloud"],
                index=0 if config.config.is_local else 1,
                label_visibility="collapsed",
            )
            config.config.set_mode(mode)
        if uploaded_files and st.button("Process and index PDFs", type="primary"):
            with st.spinner("Parsing and indexing documents..."):
                for uploaded_file in uploaded_files:
                    save_path = config.DATA_DIR / uploaded_file.name
                    save_path.write_bytes(uploaded_file.getbuffer())
                    parse_pdf(save_path)
                build_index(mode=mode)
            st.success(f"Indexed {len(uploaded_files)} PDF(s).")

    st.write("")
    tab_chat, tab_matrix = st.tabs(["💬 Academic chat", "🧮 Comparison matrix"])

    with tab_chat:
        if "messages" not in st.session_state:
            st.session_state.messages = []
        if not st.session_state.messages:
            st.caption("Ask a question about your indexed papers to get started.")
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
                    title={"text": f"Confidence · {latency:.2f}s"},
                    gauge={
                        "axis": {"range": [0, 100]},
                        "bar": {"color": "#2dd4bf"},
                        "bgcolor": "#121e30",
                        "borderwidth": 0,
                        "threshold": {
                            "line": {"color": "#f87171", "width": 2},
                            "value": config.CONFIDENCE_THRESHOLD * 100,
                        },
                    },
                ))
                gauge.update_layout(
                    height=220, margin={"t": 45, "b": 10, "l": 20, "r": 20},
                    template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(gauge, use_container_width=True)

                if response.get("mode") == "web_fallback" and not response.get("sources"):
                    st.caption(
                        "⚠️ Local confidence was below the gate and no web fallback key is configured. "
                        "Set `TAVILY_API_KEY` in your `.env`, upload more relevant papers, or lower "
                        "`CONFIDENCE_THRESHOLD` in `config.py`."
                    )

                if response["sources"]:
                    with st.expander(f"Citations ({len(response['sources'])})"):
                        for source in response["sources"]:
                            name = source.get("filename", source.get("title", "Source"))
                            meta = source.get("url") or f"relevance {source.get('score', 0):.2f}" if source.get("score") is not None else ""
                            st.markdown(
                                f"<div class='source-box'><div class='source-title'>{name}</div>"
                                f"<div class='source-meta'>{meta}</div></div>",
                                unsafe_allow_html=True,
                            )
            st.session_state.messages.append({"role": "assistant", "content": response["answer"]})

    with tab_matrix:
        st.caption("Generate a structured side-by-side comparison across every indexed paper.")
        if st.button("Generate comparison matrix", type="primary"):
            with st.spinner("Comparing indexed papers..."):
                matrix = build_comparative_matrix(mode=mode)
            st.dataframe(matrix["dataframe"], use_container_width=True)
            st.download_button("Download Markdown", matrix["markdown_table"], "comparison.md", "text/markdown")


def render_analytics() -> None:
    page_header("Quality", "Analytics", "Run the RAGAS benchmark to see faithfulness, relevance, and precision for your corpus.")
    if not require_login():
        return

    if st.button("Run RAGAS benchmark", type="primary"):
        with st.spinner("Evaluating retrieval and generation..."):
            st.session_state.evaluation = run_ragas_evaluation(mode=config.config.mode)

    evaluation = st.session_state.get("evaluation")
    if not evaluation:
        st.caption("No benchmark has been run yet in this session.")
        return

    metrics = evaluation["metrics"]
    cols = st.columns(len(metrics))
    for column, (label, value) in zip(cols, metrics.items()):
        with column:
            metric_card(label.replace("_", " ").title(), f"{value:.2f}")

    st.write("")
    charts = st.columns(2)
    with charts[0]:
        st.plotly_chart(evaluation["radar_chart"], use_container_width=True)
    with charts[1]:
        st.plotly_chart(evaluation["bar_chart"], use_container_width=True)
    st.dataframe(evaluation["dataframe"], use_container_width=True)


def render_about() -> None:
    page_header("Overview", "About Academic RAG Studio", "A local-first research assistant for exploring academic papers with citations and measurable retrieval quality.")
    st.subheader("Technology stack")
    st.dataframe(
        pd.DataFrame([
            {"Layer": "Ingestion", "Technology": "LlamaParse and hierarchical parent-child chunks"},
            {"Layer": "Retrieval", "Technology": "ChromaDB, BGE embeddings, BGE reranker base"},
            {"Layer": "Generation", "Technology": "Ollama locally or OpenAI in cloud mode"},
            {"Layer": "Correction", "Technology": "Tavily web fallback through a confidence gate"},
            {"Layer": "Evaluation", "Technology": "RAGAS metrics and Plotly visualizations"},
        ]),
        use_container_width=True,
        hide_index=True,
    )


PAGE_RENDERERS = {
    "Home": render_home,
    "Login": render_login,
    "RAG Workspace": render_workspace,
    "Analytics": render_analytics,
    "About": render_about,
}


# --------------------------------------------------------------------------
# Sidebar / navigation
# --------------------------------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "nav_page" not in st.session_state:
    st.session_state.nav_page = "Home"

with st.sidebar:
    st.markdown(
        "<div class='brand'><div class='brand-mark'>A</div>"
        "<div><div class='brand-name'>Academic RAG Studio</div>"
        "<div class='brand-sub'>RESEARCH WORKSPACE</div></div></div>",
        unsafe_allow_html=True,
    )

    nav_labels = [f"{icon}  {name}" for name, icon in PAGES] + ["🔐  Login"]
    current_label = f"{dict((n, i) for n, i in PAGES).get(st.session_state.nav_page, '🔐')}  {st.session_state.nav_page}"
    if current_label not in nav_labels:
        current_label = nav_labels[0]
    selected_label = st.radio("Navigate", nav_labels, index=nav_labels.index(current_label), label_visibility="collapsed")
    st.session_state.nav_page = selected_label.split("  ", 1)[1]

    if st.session_state.authenticated:
        name = st.session_state.get("display_name", "user")
        st.markdown(
            f"<div class='session-card'><div class='session-row'>"
            f"<div class='avatar'>{initials(name)}</div>"
            f"<div><div class='session-name'>{name}</div>"
            f"<div class='session-status'><span class='status-dot'></span>Signed in</div></div>"
            f"</div></div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div class='session-card'><div class='session-row'>"
            "<div class='avatar'>?</div>"
            "<div><div class='session-name'>Guest</div>"
            "<div class='session-status'><span class='status-dot off'></span>Not signed in</div></div>"
            "</div></div>",
            unsafe_allow_html=True,
        )

PAGE_RENDERERS[st.session_state.nav_page]()
