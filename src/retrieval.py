import logging
from typing import List, Dict, Tuple, Optional, Any
from pathlib import Path

from llama_index.core import VectorStoreIndex, StorageContext, Settings
from llama_index.core.retrievers import AutoMergingRetriever
from llama_index.core.postprocessor import SentenceTransformerRerank
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.core.schema import NodeWithScore, TextNode
from llama_index.llms.ollama import Ollama
from llama_index.llms.openai import OpenAI
import chromadb
from llama_index.vector_stores.chroma import ChromaVectorStore

import config
from src.indexing import get_embedding_model

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("retrieval")

import math

_RERANKER_CACHE = {}
_CHROMA_CLIENT_CACHE = {}
_LLM_CACHE = {}

def get_cached_reranker(model_name: str, top_n: int):
    key = f"{model_name}_{top_n}"
    if key not in _RERANKER_CACHE:
        logger.info(f"Initializing & caching reranker model: {model_name}...")
        _RERANKER_CACHE[key] = SentenceTransformerRerank(
            model=model_name,
            top_n=top_n
        )
    return _RERANKER_CACHE[key]

def sigmoid_score(raw_score: float) -> float:
    """Applies sigmoid function to map raw cross-encoder logits into [0, 1] range."""
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

def get_llm(mode: str = None):
    mode = mode or config.config.mode
    if mode in _LLM_CACHE:
        return _LLM_CACHE[mode]
    if mode == "cloud" and config.OPENAI_API_KEY:
        logger.info("Using OpenAI LLM (gpt-4o-mini)")
        llm = OpenAI(model=config.CLOUD_LLM_MODEL, api_key=config.OPENAI_API_KEY)
    else:
        logger.info(f"Using Ollama local LLM ({config.OLLAMA_MODEL}) at {config.OLLAMA_BASE_URL}")
        llm = Ollama(
            model=config.OLLAMA_MODEL,
            base_url=config.OLLAMA_BASE_URL,
            request_timeout=config.OLLAMA_REQUEST_TIMEOUT,
        )
    _LLM_CACHE[mode] = llm
    return llm

def generate_sub_queries(query: str, mode: str = None, count: int = 3) -> List[str]:
    """Uses LLM to expand input query into multiple diverse sub-queries."""
    llm = get_llm(mode)
    prompt = (
        f"Formulate {count} diverse academic search sub-queries for: \"{query}\"\n"
        f"Output ONLY {count} sub-queries, one per line."
    )
    try:
        response = llm.complete(prompt)
        sub_queries = [line.strip("- *1234567890. ") for line in response.text.strip().split("\n") if line.strip()]
        if len(sub_queries) < count:
            sub_queries.append(query)
        logger.info(f"Generated sub-queries: {sub_queries[:count]}")
        return sub_queries[:count]
    except Exception as e:
        logger.warning(f"Sub-query expansion skipped ({e}). Using original query.")
        return [query]

def retrieve_and_rerank(
    query: str,
    persist_dir: Path = config.CHROMADB_DIR,
    collection_name: str = "academic_rag",
    top_k_vector: int = config.TOP_K_RETRIEVAL,
    top_k_rerank: int = config.TOP_K_RERANK,
    mode: str = None
) -> List[Dict[str, Any]]:
    persist_dir = Path(persist_dir)
    docstore_path = persist_dir / "docstore.json"
    
    embed_model = get_embedding_model(mode)
    Settings.embed_model = embed_model
    
    persist_str = str(persist_dir)
    if persist_str not in _CHROMA_CLIENT_CACHE:
        _CHROMA_CLIENT_CACHE[persist_str] = chromadb.PersistentClient(path=persist_str)
    db = _CHROMA_CLIENT_CACHE[persist_str]
    
    chroma_collection = db.get_or_create_collection(collection_name)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    
    docstore = SimpleDocumentStore()
    if docstore_path.exists():
        try:
            docstore = SimpleDocumentStore.from_persist_path(str(docstore_path))
        except Exception as e:
            logger.warning(f"Could not load docstore: {e}")
        
    storage_context = StorageContext.from_defaults(
        vector_store=vector_store,
        docstore=docstore
    )
    
    index = VectorStoreIndex.from_vector_store(
        vector_store=vector_store,
        storage_context=storage_context,
        embed_model=embed_model
    )
    
    base_retriever = index.as_retriever(similarity_top_k=top_k_vector)
    automerge_retriever = AutoMergingRetriever(
        vector_retriever=base_retriever,
        storage_context=storage_context,
        verbose=False
    )
    
    # Step B: Sub-query expansion
    sub_queries = generate_sub_queries(query, mode=mode)
    all_queries = list(set([query] + sub_queries))
    
    # Vector Search & Collect Parent/Leaf Nodes
    raw_nodes_map: Dict[str, NodeWithScore] = {}
    for q in all_queries:
        retrieved_nodes = automerge_retriever.retrieve(q)
        for n in retrieved_nodes:
            if n.node.node_id not in raw_nodes_map or (n.score or 0.0) > (raw_nodes_map[n.node.node_id].score or 0.0):
                raw_nodes_map[n.node.node_id] = n
                
    unique_nodes = list(raw_nodes_map.values())
    logger.info(f"Retrieved {len(unique_nodes)} unique candidate nodes across sub-queries.")
    
    if not unique_nodes:
        logger.warning("No nodes retrieved from vector search.")
        return []
        
    # Step C: Rerank using BGE Reranker with singleton model cache
    logger.info(f"Reranking {len(unique_nodes)} candidate nodes using {config.LOCAL_RERANK_MODEL}...")
    try:
        reranker = get_cached_reranker(config.LOCAL_RERANK_MODEL, top_k_rerank)
        reranked_nodes = reranker.postprocess_nodes(unique_nodes, query_str=query)
    except Exception as e:
        logger.warning(f"SentenceTransformerRerank error: {e}. Falling back to top vector similarity scores.")
        unique_nodes.sort(key=lambda x: x.score or 0.0, reverse=True)
        reranked_nodes = unique_nodes[:top_k_rerank]
        
    results = []
    for node_score in reranked_nodes:
        node = node_score.node
        meta = node.metadata or {}
        raw_val = node_score.score
        # Compute normalized sigmoid score for confidence thresholding
        norm_score = sigmoid_score(raw_val)
        results.append({
            "node_id": node.node_id,
            "text": node.get_content(),
            "score": norm_score,
            "raw_score": raw_val,
            "source_filename": meta.get("source_filename", "academic_paper.pdf"),
            "file_path": meta.get("file_path", ""),
            "metadata": meta
        })
        
    return results

if __name__ == "__main__":
    test_q = "What are the core transformer attention mechanisms used?"
    logger.info(f"Testing retrieval for: '{test_q}'")
    top_chunks = retrieve_and_rerank(test_q)
    for idx, c in enumerate(top_chunks, 1):
        logger.info(f"Rank {idx} [Score: {c['score']:.4f}] from {c['source_filename']}:\n{c['text'][:150]}...\n")
