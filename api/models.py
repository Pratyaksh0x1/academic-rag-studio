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
    mode: Optional[str] = "local" # "local" or "cloud"

class QueryResponse(BaseModel):
    query: str
    answer: str
    mode: str
    confidence_score: float
    sources: List[Dict[str, Any]]

class MatrixRequest(BaseModel):
    mode: Optional[str] = "local"
    files: Optional[List[str]] = None
