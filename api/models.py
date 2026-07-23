from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class UserRegister(BaseModel):
    username: str = Field(..., min_length=3)
    password: str = Field(..., min_length=4)


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class QueryRequest(BaseModel):
    query: str
    mode: Optional[str] = "local"


class SourceItem(BaseModel):
    filename: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    score: Optional[float] = None
    text_snippet: Optional[str] = None
    snippet: Optional[str] = None
    type: Optional[str] = None


class RetrievedChunk(BaseModel):
    node_id: str
    text: str
    score: float
    source_filename: str
    file_path: Optional[str] = None


class QueryResponse(BaseModel):
    query: str
    answer: str
    mode: str
    confidence_score: float
    sources: List[Dict[str, Any]]
    retrieved_chunks: List[Dict[str, Any]] = []
    warnings: List[str] = []


class MatrixRequest(BaseModel):
    mode: Optional[str] = "local"
    files: Optional[List[str]] = None


class ModeRequest(BaseModel):
    mode: str


class IngestResponse(BaseModel):
    message: str
    parse_details: Dict[str, Any]
    index_stats: Dict[str, Any]


class StatusResponse(BaseModel):
    status: str
    mode: str
    index_stats: Dict[str, Any]
    ollama: Dict[str, Any]
    services: Dict[str, bool]
