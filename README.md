# 🎓 Hyper-Personalized Academic RAG Bot

Production-grade Academic RAG system featuring **Hierarchical Parent-Child Chunking**, **Multi-Query Expansion**, **BGE Reranking**, **Corrective RAG (CRAG) Web Fallback**, **Multi-Document Comparative Analysis**, **RAGAS Evaluation Benchmarking**, and a **100% Offline (Local) ↔ Cloud Hybrid Toggle**.

---

## 🏗️ Architecture Stack

| Layer | Component |
|---|---|
| PDF Ingestion | **LlamaParse** (primary) + Unstructured / PyPDF (fallback) |
| Chunking | LlamaIndex `HierarchicalNodeParser` (Parent 1024 / Child 256 tokens) |
| Embeddings | `BAAI/bge-large-en-v1.5` (Local) / `text-embedding-3-large` (Cloud) |
| Vector Store | **ChromaDB** persistent vector collection |
| Reranker | `BAAI/bge-reranker-large` (Local) / SentenceTransformer |
| Local LLM | **Ollama + Llama 3** |
| Cloud LLM | **GPT-4o-mini** |
| Web Search (CRAG) | **Tavily API** |
| Evaluation | **RAGAS** (Faithfulness, Context Precision, Answer Relevance) |
| Frontend UI | **Streamlit** (Multi-tab Dashboard with Live Hybrid Switch) |
| Backend API | **FastAPI** + JWT Auth + MongoDB |

---

## ⚡ Quickstart Guide

### 1. Environment Setup
```bash
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Fill in optional keys:
- `LLAMA_CLOUD_API_KEY`: For LlamaParse markdown extraction.
- `OPENAI_API_KEY`: For Cloud Mode execution.
- `TAVILY_API_KEY`: For Corrective RAG live web search fallback.

### 3. Run Streamlit Dashboard
```bash
streamlit run app.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## 🚀 API & Docker Deployment

### Run FastAPI Server
```bash
uvicorn api.main:app --reload --port 8000
```
Interactive API documentation available at: [http://localhost:8000/docs](http://localhost:8000/docs)

### Docker Compose
```bash
docker-compose up --build
```

---

## 📊 Panel Presentation Tips
- **Live Hybrid Toggle Demo**: Switch between **Local Mode (Ollama+BGE)** and **Cloud Mode (GPT-4o-mini)** in the Streamlit sidebar to prove 0% API dependency when offline.
- **Show RAGAS Benchmark Chart**: Highlight the numeric evaluation scores in Tab 3.
- **Live PDF Upload Challenge**: Let examiners upload their own academic PDF live and observe markdown parsing & citation accuracy.
