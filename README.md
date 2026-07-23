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
| Frontend UI | **React 18 + TypeScript 5 + Three.js + Framer Motion** (3D Interactive Dashboard) |
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

### 3. Run React Frontend + FastAPI Backend
From the `frontend/` directory:
```bash
npm install
npm run dev
```

In a separate terminal, run the FastAPI server:
```bash
uvicorn api.main:app --reload --port 8000
```
Open [http://localhost:5173](http://localhost:5173) for the dev frontend or [http://localhost:8000](http://localhost:8000) for the production build.

---

## 🚀 Production Deployment

### Docker Compose
```bash
docker-compose up --build
```
Serves the production React build on port 8000.

---

## 📊 Key Features
- **Live Hybrid Toggle Demo**: Switch between **Local Mode (Ollama+BGE)** and **Cloud Mode (GPT-4o-mini)** to prove 0% API dependency when offline.
- **3D Knowledge Graph**: Interactive Three.js visualization of your indexed research space.
- **RAGAS Benchmark Chart**: Highlight numeric evaluation scores.
- **Live PDF Upload**: Let users upload academic PDFs live and observe markdown parsing & citation accuracy.
