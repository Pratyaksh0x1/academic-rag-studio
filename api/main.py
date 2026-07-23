import shutil
from pathlib import Path
from typing import List

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import config
from api.auth import create_jwt_token, hash_password, verify_jwt_token
from api.models import (
    IngestResponse,
    MatrixRequest,
    ModeRequest,
    QueryRequest,
    QueryResponse,
    StatusResponse,
    TokenResponse,
    UserLogin,
    UserRegister,
)
from src.comparative_matrix import build_comparative_matrix
from src.database import db_handler
from src.evaluate import run_ragas_evaluation
from src.generation import generate_answer
from src.indexing import build_index, get_index_stats, validate_index_mode
from src.ingestion import parse_pdf
from src.retrieval import RetrievalError, check_ollama_health, retrieve_and_rerank

FRONTEND_DIST = config.BASE_DIR / "frontend" / "dist"

app = FastAPI(
    title="Academic RAG Studio API",
    description="Production-grade RAG platform for academic PDF research with offline-first retrieval.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/status", response_model=StatusResponse)
def system_status():
    index_stats = get_index_stats()
    ollama = check_ollama_health()
    compatible, message = validate_index_mode(config.config.mode)
    return StatusResponse(
        status="online",
        mode=config.config.mode,
        index_stats={**index_stats, "mode_compatible": compatible, "mode_message": message},
        ollama=ollama,
        services={
            "openai_configured": bool(config.OPENAI_API_KEY),
            "tavily_configured": bool(config.TAVILY_API_KEY),
            "auth_disabled": config.DISABLE_AUTH,
            "frontend_built": FRONTEND_DIST.exists(),
        },
    )


@app.post("/api/mode")
def set_mode(req: ModeRequest, username: str = Depends(verify_jwt_token)):
    if req.mode not in ("local", "cloud"):
        raise HTTPException(status_code=400, detail="Mode must be 'local' or 'cloud'.")
    config.config.set_mode(req.mode)
    compatible, message = validate_index_mode(req.mode)
    return {
        "mode": config.config.mode,
        "username": username,
        "index_compatible": compatible,
        "message": message,
    }


@app.get("/api/documents")
def list_documents(username: str = Depends(verify_jwt_token)):
    stats = get_index_stats()
    return {"user": username, **stats}


@app.post("/auth/register", response_model=TokenResponse)
def register(user: UserRegister):
    pwd_hash = hash_password(user.password)
    success = db_handler.create_user(user.username, pwd_hash)
    if not success:
        raise HTTPException(status_code=400, detail="Username already exists.")
    token = create_jwt_token(user.username)
    return {"access_token": token, "token_type": "bearer"}


@app.post("/auth/login", response_model=TokenResponse)
def login(user: UserLogin):
    stored = db_handler.get_user(user.username)
    if not stored or stored.get("password_hash") != hash_password(user.password):
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    token = create_jwt_token(user.username)
    return {"access_token": token, "token_type": "bearer"}


@app.post("/api/ingest", response_model=IngestResponse)
async def upload_and_index_pdf(
    file: UploadFile = File(...),
    rebuild: bool = False,
    username: str = Depends(verify_jwt_token),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    save_path = config.DATA_DIR / file.filename
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    parse_result = parse_pdf(save_path)
    build_index(mode=config.config.mode, rebuild=rebuild)
    stats = get_index_stats()

    return IngestResponse(
        message=f"Successfully ingested and indexed {file.filename}",
        parse_details=parse_result,
        index_stats=stats,
    )


@app.post("/api/query", response_model=QueryResponse)
def query_rag(req: QueryRequest, username: str = Depends(verify_jwt_token)):
    mode = req.mode or config.config.mode
    config.config.set_mode(mode)
    response = generate_answer(req.query, mode=mode)

    if not config.DISABLE_AUTH:
        db_handler.save_chat(
            username=username,
            query=req.query,
            answer=response["answer"],
            sources=response["sources"],
            mode=response["mode"],
        )

    return QueryResponse(
        query=response["query"],
        answer=response["answer"],
        mode=response["mode"],
        confidence_score=response["confidence_score"],
        sources=response["sources"],
        retrieved_chunks=response.get("retrieved_chunks", []),
        warnings=response.get("warnings", []),
    )


@app.post("/api/retrieve")
def retrieve_only(req: QueryRequest, username: str = Depends(verify_jwt_token)):
    mode = req.mode or config.config.mode
    try:
        chunks = retrieve_and_rerank(req.query, mode=mode)
    except RetrievalError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"user": username, "query": req.query, "chunks": chunks}


@app.post("/api/matrix")
def get_comparative_matrix(req: MatrixRequest, username: str = Depends(verify_jwt_token)):
    matrix_res = build_comparative_matrix(file_list=req.files, mode=req.mode)
    return {
        "user": username,
        "markdown_table": matrix_res["markdown_table"],
        "records": matrix_res["dataframe"].to_dict(orient="records"),
    }


@app.get("/api/evaluate")
def run_evaluation(username: str = Depends(verify_jwt_token)):
    eval_res = run_ragas_evaluation(mode=config.config.mode)
    return {"user": username, "metrics": eval_res["metrics"]}


@app.post("/api/reindex")
def reindex_documents(
    rebuild: bool = True,
    username: str = Depends(verify_jwt_token),
):
    build_index(mode=config.config.mode, rebuild=rebuild)
    return {"user": username, "message": "Re-index completed.", "index_stats": get_index_stats()}


if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/")
    def serve_frontend():
        return FileResponse(FRONTEND_DIST / "index.html")

    @app.get("/{full_path:path}")
    def serve_frontend_routes(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("auth/"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = FRONTEND_DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
else:

    @app.get("/")
    def read_root():
        return {
            "status": "online",
            "service": "Academic RAG Studio API",
            "mode": config.config.mode,
            "frontend": "Build the React frontend with `cd frontend && npm install && npm run build`.",
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
