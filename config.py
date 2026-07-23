import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
CHROMADB_DIR = BASE_DIR / "chromadb_store"
DATA_DIR = BASE_DIR / "data"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CHROMADB_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# API Keys
LLAMA_CLOUD_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# MongoDB Config
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "academic-rag-secret-key")

# Ollama Config
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

# Local Models
LOCAL_EMBEDDING_MODEL = "BAAI/bge-large-en-v1.5"
LOCAL_RERANK_MODEL = "BAAI/bge-reranker-base"

# Cloud Models
CLOUD_EMBEDDING_MODEL = "text-embedding-3-large"
CLOUD_LLM_MODEL = "gpt-4o-mini"

# Chunking Parameters
PARENT_CHUNK_SIZE = 1024
CHILD_CHUNK_SIZE = 256
CHUNK_OVERLAP = 20

# Reranking & CRAG Thresholds
CONFIDENCE_THRESHOLD = 0.65
TOP_K_RETRIEVAL = 15
TOP_K_RERANK = 5
OLLAMA_REQUEST_TIMEOUT = 3.0

class AppConfig:
    def __init__(self, mode: str = None):
        self.mode = mode or os.getenv("DEFAULT_MODE", "local").lower()

    def set_mode(self, mode: str):
        if mode in ["local", "cloud"]:
            self.mode = mode

    @property
    def is_local(self) -> bool:
        return self.mode == "local"

config = AppConfig()
