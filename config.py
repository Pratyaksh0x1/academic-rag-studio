import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
CHROMADB_DIR = BASE_DIR / "chromadb_store"
DATA_DIR = BASE_DIR / "data"
INDEX_META_PATH = CHROMADB_DIR / "index_meta.json"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CHROMADB_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

def _clean_env_key(name: str) -> str:
    """Read an API key from the environment, treating unfilled placeholder
    values (e.g. 'your_openai_api_key_here', left over from .env.example)
    as if the key were not set at all."""
    value = os.getenv(name, "").strip()
    if not value or value.lower().startswith("your_") or value.endswith("_here"):
        return ""
    return value


# API Keys
LLAMA_CLOUD_API_KEY = _clean_env_key("LLAMA_CLOUD_API_KEY")
OPENAI_API_KEY = _clean_env_key("OPENAI_API_KEY")
TAVILY_API_KEY = _clean_env_key("TAVILY_API_KEY")

# MongoDB Config
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "academic-rag-secret-key")
DISABLE_AUTH = os.getenv("DISABLE_AUTH", "false").lower() in ("1", "true", "yes")

# Ollama Config
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
OLLAMA_REQUEST_TIMEOUT = float(os.getenv("OLLAMA_REQUEST_TIMEOUT", "120"))

# Local Models
LOCAL_EMBEDDING_MODEL = os.getenv("LOCAL_EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
LOCAL_RERANK_MODEL = os.getenv("LOCAL_RERANK_MODEL", "BAAI/bge-reranker-base")

# Cloud Models (small embedding reduces OpenAI quota usage)
CLOUD_EMBEDDING_MODEL = os.getenv("CLOUD_EMBEDDING_MODEL", "text-embedding-3-small")
CLOUD_LLM_MODEL = os.getenv("CLOUD_LLM_MODEL", "gpt-4o-mini")

# Chunking Parameters
PARENT_CHUNK_SIZE = int(os.getenv("PARENT_CHUNK_SIZE", "1024"))
CHILD_CHUNK_SIZE = int(os.getenv("CHILD_CHUNK_SIZE", "256"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "20"))

# Reranking & CRAG Thresholds (local reranker logits map lower via sigmoid)
CONFIDENCE_THRESHOLD_LOCAL = float(os.getenv("CONFIDENCE_THRESHOLD_LOCAL", "0.35"))
CONFIDENCE_THRESHOLD_CLOUD = float(os.getenv("CONFIDENCE_THRESHOLD_CLOUD", "0.55"))
CONFIDENCE_THRESHOLD = CONFIDENCE_THRESHOLD_LOCAL
TOP_K_RETRIEVAL = int(os.getenv("TOP_K_RETRIEVAL", "15"))
TOP_K_RERANK = int(os.getenv("TOP_K_RERANK", "5"))
MIN_RETRIEVAL_SCORE = float(os.getenv("MIN_RETRIEVAL_SCORE", "0.15"))
MIN_RETRIEVAL_SCORE_LOCAL = float(os.getenv("MIN_RETRIEVAL_SCORE_LOCAL", "0.02"))
MIN_RETRIEVAL_SCORE_CLOUD = float(os.getenv("MIN_RETRIEVAL_SCORE_CLOUD", "0.15"))

# Retry / resilience
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
LLM_RETRY_BASE_DELAY = float(os.getenv("LLM_RETRY_BASE_DELAY", "2.0"))

COLLECTION_NAME = "academic_rag"


def confidence_threshold_for_mode(mode: str = None) -> float:
    mode = (mode or AppConfig().mode).lower()
    return CONFIDENCE_THRESHOLD_CLOUD if mode == "cloud" else CONFIDENCE_THRESHOLD_LOCAL


def min_retrieval_score_for_mode(mode: str = None) -> float:
    mode = (mode or AppConfig().mode).lower()
    return MIN_RETRIEVAL_SCORE_CLOUD if mode == "cloud" else MIN_RETRIEVAL_SCORE_LOCAL


def load_index_metadata() -> dict:
    if not INDEX_META_PATH.exists():
        return {}
    try:
        return json.loads(INDEX_META_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_index_metadata(meta: dict) -> None:
    INDEX_META_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_META_PATH.write_text(json.dumps(meta, indent=2), encoding="utf-8")


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
