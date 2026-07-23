import os
import shutil
from pathlib import Path
from typing import List
from fastapi import FastAPI, Depends, File, UploadFile, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

import config
from src.database import db_handler
from api.models import UserRegister, UserLogin, TokenResponse, QueryRequest, QueryResponse, MatrixRequest
from api.auth import hash_password, create_jwt_token, verify_jwt_token
from src.ingestion import parse_pdf
from src.indexing import build_index
from src.generation import generate_answer
from src.comparative_matrix import build_comparative_matrix
from src.evaluate import run_ragas_evaluation

app = FastAPI(
    title="Hyper-Personalized Academic RAG API",
    description="Production-grade FastAPI endpoints for PDF ingestion, Parent-Child Indexing, RAG generation, & Matrix comparison.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "Hyper-Personalized Academic RAG Bot API",
        "mode": config.config.mode
    }

# Auth Endpoints
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

# Ingestion & Indexing Endpoint
@app.post("/api/ingest")
def upload_and_index_pdf(
    file: UploadFile = File(...),
    username: str = Depends(verify_jwt_token)
):
    save_path = config.DATA_DIR / file.filename
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    parse_result = parse_pdf(save_path)
    build_index(mode=config.config.mode)
    
    return {
        "message": f"Successfully ingested and indexed {file.filename}",
        "user": username,
        "parse_details": parse_result
    }

# Query & Generation Endpoint
@app.post("/api/query", response_model=QueryResponse)
def query_rag(
    req: QueryRequest,
    username: str = Depends(verify_jwt_token)
):
    mode = req.mode or config.config.mode
    response = generate_answer(req.query, mode=mode)
    
    # Log to MongoDB
    db_handler.save_chat(
        username=username,
        query=req.query,
        answer=response["answer"],
        sources=response["sources"],
        mode=response["mode"]
    )
    
    return QueryResponse(
        query=response["query"],
        answer=response["answer"],
        mode=response["mode"],
        confidence_score=response["confidence_score"],
        sources=response["sources"]
    )

# Comparative Matrix Endpoint
@app.post("/api/matrix")
def get_comparative_matrix(
    req: MatrixRequest,
    username: str = Depends(verify_jwt_token)
):
    matrix_res = build_comparative_matrix(file_list=req.files, mode=req.mode)
    return {
        "user": username,
        "markdown_table": matrix_res["markdown_table"],
        "records": matrix_res["dataframe"].to_dict(orient="records")
    }

# Evaluation Endpoint
@app.get("/api/evaluate")
def run_evaluation(username: str = Depends(verify_jwt_token)):
    eval_res = run_ragas_evaluation(mode=config.config.mode)
    return {
        "user": username,
        "metrics": eval_res["metrics"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
