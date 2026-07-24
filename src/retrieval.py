import logging
import math
from typing import List, Dict, Any, Optional
from pathlib import Path

from llama_index.core import VectorStoreIndex, StorageContext, Settings
from llama_index.core.retrievers import AutoMergingRetriever
from llama_index.core.postprocessor import SentenceTransformerRerank
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.core.schema import NodeWithScore
from llama_index.llms.ollama import Ollama
from llama_index.llms.openai import OpenAI
import chromadb
from llama_index.vector_stores.chroma import ChromaVectorStore

import config
from src.indexing import get_embedding_model, validate_index_mode
from src.llm_utils import complete_with_fallback

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("retrieval")

_RERANKER_CACHE = {}
_CHROMA_CLIENT_CACHE = {}
_LLM_CACHE = {}


class RetrievalError(Exception):
    """Raised when retrieval cannot proceed due to configuration or index issues."""


def get_cached_reranker(model_name: str, top_n: int):
    key = f"{model_name}_{top_n}"
    if key not in _RERANKER_CACHE:
        logger.info("Initializing reranker model: %s", model_name)
        _RERANKER_CACHE[key] = SentenceTransformerRerank(model=model_name, top_n=top_n)
    return _RERANKER_CACHE[key]


def sigmoid_score(raw_score: float) -> float:
    if raw_score is None:
        return 0.0
    try:
        value = float(raw_score)
        if value >= 0:
            sigmoid = 1.0 / (1.0 + math.exp(-value))
        else:
            exp_value = math.exp(value)
            sigmoid = exp_value / (1.0 + exp_value)
        return round(min(1.0, max(0.0, sigmoid)), 4)
    except Exception:
        return 0.5


def get_threshold(mode: str = None) -> float:
    mode = mode or config.config.mode
    if mode == "cloud":
        return config.MIN_RETRIEVAL_SCORE_CLOUD
    return config.MIN_RETRIEVAL_SCORE_LOCAL


def normalize_vector_score(score: Optional[float]) -> float:
    if score is None:
        return 0.0
    value = float(score)
    if 0.0 <= value <= 1.0:
        return round(value, 4)
    # Chroma returns distance for some setups; convert to similarity-ish range
    return round(max(0.0, 1.0 / (1.0 + abs(value))), 4)


def get_llm(mode: str = None):
    mode = mode or config.config.mode
    if mode in _LLM_CACHE:
        return _LLM_CACHE[mode]
    if mode == "cloud" and config.OPENAI_API_KEY:
        logger.info("Using OpenAI LLM (%s)", config.CLOUD_LLM_MODEL)
        llm = OpenAI(model=config.CLOUD_LLM_MODEL, api_key=config.OPENAI_API_KEY)
    else:
        logger.info("Using Ollama local LLM (%s) at %s", config.OLLAMA_MODEL, config.OLLAMA_BASE_URL)
        llm = Ollama(
            model=config.OLLAMA_MODEL,
            base_url=config.OLLAMA_BASE_URL,
            request_timeout=config.OLLAMA_REQUEST_TIMEOUT,
        )
    _LLM_CACHE[mode] = llm
    return llm


def check_ollama_health() -> dict:
    import urllib.request
    import json

    url = f"{config.OLLAMA_BASE_URL.rstrip('/')}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
            models = [m.get("name", "") for m in payload.get("models", [])]
            return {
                "online": True,
                "models": models,
                "configured_model": config.OLLAMA_MODEL,
                "model_available": any(config.OLLAMA_MODEL in name for name in models),
            }
    except Exception as exc:
        return {"online": False, "error": str(exc), "configured_model": config.OLLAMA_MODEL}


def generate_sub_queries(query: str, mode: str = None, count: int = 3) -> List[str]:
    llm = get_llm(mode)
    prompt = (
        f"Formulate {count} diverse academic search sub-queries for: \"{query}\"\n"
        f"Output ONLY {count} sub-queries, one per line."
    )
    try:
        text = complete_with_fallback(llm, prompt, mode=mode, label="sub-query expansion")
        sub_queries = [
            line.strip("- *1234567890. ")
            for line in text.strip().split("\n")
            if line.strip()
        ]
        if not sub_queries:
            return [query]
        if len(sub_queries) < count:
            sub_queries.append(query)
        logger.info("Generated sub-queries: %s", sub_queries[:count])
        return sub_queries[:count]
    except Exception as exc:
        logger.warning("Sub-query expansion skipped (%s). Using original query.", exc)
        return [query]


def retrieve_and_rerank(
    query: str,
    persist_dir: Path = config.CHROMADB_DIR,
    collection_name: str = config.COLLECTION_NAME,
    top_k_vector: int = config.TOP_K_RETRIEVAL,
    top_k_rerank: int = config.TOP_K_RERANK,
    mode: str = None,
) -> List[Dict[str, Any]]:
    mode = mode or config.config.mode
    persist_dir = Path(persist_dir)
    docstore_path = persist_dir / "docstore.json"

    compatible, message = validate_index_mode(mode)
    if not compatible:
        raise RetrievalError(message)
    if message != "Index mode compatible.":
        logger.info(message)

    embed_model = get_embedding_model(mode)
    Settings.embed_model = embed_model

    persist_str = str(persist_dir)
    if persist_str not in _CHROMA_CLIENT_CACHE:
        _CHROMA_CLIENT_CACHE[persist_str] = chromadb.PersistentClient(path=persist_str)
    db = _CHROMA_CLIENT_CACHE[persist_str]

    chroma_collection = db.get_or_create_collection(collection_name)
    if chroma_collection.count() == 0:
        logger.warning("Vector store is empty. Upload and index PDFs first.")
        return []

    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

    docstore = SimpleDocumentStore()
    if docstore_path.exists():
        try:
            docstore = SimpleDocumentStore.from_persist_path(str(docstore_path))
        except Exception as exc:
            logger.warning("Could not load docstore: %s", exc)

    storage_context = StorageContext.from_defaults(
        vector_store=vector_store,
        docstore=docstore,
    )

    index = VectorStoreIndex.from_vector_store(
        vector_store=vector_store,
        storage_context=storage_context,
        embed_model=embed_model,
    )

    base_retriever = index.as_retriever(similarity_top_k=top_k_vector)
    automerge_retriever = AutoMergingRetriever(
        vector_retriever=base_retriever,
        storage_context=storage_context,
        verbose=False,
    )

    sub_queries = generate_sub_queries(query, mode=mode)
    all_queries = list(dict.fromkeys([query, *sub_queries]))

    raw_nodes_map: Dict[str, NodeWithScore] = {}
    for q in all_queries:
        try:
            retrieved_nodes = automerge_retriever.retrieve(q)
        except Exception as exc:
            logger.warning("AutoMergingRetriever failed for query '%s': %s", q, exc)
            try:
                retrieved_nodes = base_retriever.retrieve(q)
                logger.info("Fell back to base retriever for query '%s'.", q)
            except Exception as fallback_exc:
                logger.warning("Base retriever also failed for query '%s': %s", q, fallback_exc)
                continue
        for node in retrieved_nodes:
            existing = raw_nodes_map.get(node.node.node_id)
            if not existing or (node.score or 0.0) > (existing.score or 0.0):
                raw_nodes_map[node.node.node_id] = node

    unique_nodes = list(raw_nodes_map.values())
    logger.info("Retrieved %s unique candidate nodes from %s queries.", len(unique_nodes), len(all_queries))
    if not unique_nodes:
        logger.warning("No nodes retrieved. Check collection count (%s) and embedding model compatibility.", chroma_collection.count())
        return []

    threshold = get_threshold(mode)
    logger.info("Using retrieval score threshold: %.4f for mode '%s'", threshold, mode)

    # IMPORTANT: capture the original vector-similarity scores BEFORE reranking.
    # The reranker postprocessor overwrites NodeWithScore.score in place with the
    # rerank score, so if we read vector scores from the same objects afterward
    # we're actually reading the rerank score twice (rerank counted at both 0.7
    # and 0.3 weight, vector score never used). Snapshot by node_id first.
    original_vector_scores = {
        node_score.node.node_id: node_score.score for node_score in unique_nodes
    }

    try:
        reranker = get_cached_reranker(config.LOCAL_RERANK_MODEL, top_k_rerank)
        reranked_nodes = reranker.postprocess_nodes(unique_nodes, query_str=query)
    except Exception as exc:
        logger.warning("Reranker failed (%s). Falling back to vector scores.", exc)
        unique_nodes.sort(key=lambda x: x.score or 0.0, reverse=True)
        reranked_nodes = unique_nodes[:top_k_rerank]

    threshold = get_threshold(mode)

    results = []
    for node_score in reranked_nodes:
        node = node_score.node
        meta = node.metadata or {}
        raw_val = node_score.score
        rerank_norm = sigmoid_score(raw_val)
        vector_norm = normalize_vector_score(original_vector_scores.get(node.node_id))
        combined_score = round((rerank_norm * 0.7) + (vector_norm * 0.3), 4)

        if combined_score < threshold:
            continue

        results.append(
            {
                "node_id": node.node_id,
                "text": node.get_content(),
                "score": combined_score,
                "raw_score": raw_val,
                "source_filename": meta.get("source_filename", "academic_paper.pdf"),
                "file_path": meta.get("file_path", ""),
                "metadata": meta,
            }
        )

    results.sort(key=lambda item: item["score"], reverse=True)
    logger.info("Returning %s results after filtering (threshold %.4f).", len(results), threshold)
    return results[:top_k_rerank]


if __name__ == "__main__":
    test_q = "What are the core transformer attention mechanisms used?"
    logger.info("Testing retrieval for: '%s'", test_q)
    chunks = retrieve_and_rerank(test_q)
    for idx, chunk in enumerate(chunks, 1):
        logger.info(
            "Rank %s [Score: %s] from %s:\n%s...\n",
            idx,
            chunk["score"],
            chunk["source_filename"],
            chunk["text"][:150],
        )
