import os
import logging
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
import chromadb

from llama_index.core import SimpleDirectoryReader, StorageContext, VectorStoreIndex, Document
from llama_index.core.node_parser import HierarchicalNodeParser, get_leaf_nodes, get_root_nodes
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.core.storage.index_store import SimpleIndexStore
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core.settings import Settings

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("indexing")

_EMBED_MODEL_CACHE = {}

def get_embedding_model(mode: str = None):
    mode = mode or config.config.mode
    if mode in _EMBED_MODEL_CACHE:
        return _EMBED_MODEL_CACHE[mode]

    if mode == "cloud":
        if not config.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not set. Falling back to local BGE embedding model.")
            model = HuggingFaceEmbedding(model_name=config.LOCAL_EMBEDDING_MODEL)
        else:
            logger.info(f"Using Cloud OpenAI Embedding model: {config.CLOUD_EMBEDDING_MODEL}")
            model = OpenAIEmbedding(model=config.CLOUD_EMBEDDING_MODEL, api_key=config.OPENAI_API_KEY)
    else:
        logger.info(f"Using Local HuggingFace Embedding model: {config.LOCAL_EMBEDDING_MODEL}")
        model = HuggingFaceEmbedding(model_name=config.LOCAL_EMBEDDING_MODEL)
        
    _EMBED_MODEL_CACHE[mode] = model
    return model

def build_hierarchical_nodes(documents: List[Document]) -> Tuple[List[Any], List[Any]]:
    """Creates parent (1024) and child (256) chunks with parent-child relationship maintained."""
    node_parser = HierarchicalNodeParser.from_defaults(
        chunk_sizes=[config.PARENT_CHUNK_SIZE, config.CHILD_CHUNK_SIZE],
        chunk_overlap=config.CHUNK_OVERLAP
    )
    nodes = node_parser.get_nodes_from_documents(documents)
    leaf_nodes = get_leaf_nodes(nodes)
    root_nodes = get_root_nodes(nodes)
    logger.info(f"Generated {len(nodes)} total nodes: {len(root_nodes)} parent nodes, {len(leaf_nodes)} leaf (child) nodes.")
    return nodes, leaf_nodes

def build_index(
    docs_folder: Path = config.OUTPUT_DIR,
    persist_dir: Path = config.CHROMADB_DIR,
    collection_name: str = "academic_rag",
    mode: str = None
) -> Tuple[VectorStoreIndex, SimpleDocumentStore]:
    """
    Loads parsed markdown files, creates parent-child nodes, embeds child nodes into ChromaDB,
    and stores full node docstore locally for parent retrieval.
    Incremental update check included.
    """
    docs_folder = Path(docs_folder)
    persist_dir = Path(persist_dir)
    persist_dir.mkdir(parents=True, exist_ok=True)

    embed_model = get_embedding_model(mode)
    Settings.embed_model = embed_model

    # ChromaDB persistent client setup
    db = chromadb.PersistentClient(path=str(persist_dir))
    chroma_collection = db.get_or_create_collection(collection_name)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

    # Document store for parent nodes retrieval
    docstore_path = persist_dir / "docstore.json"
    docstore = SimpleDocumentStore()
    if docstore_path.exists():
        try:
            docstore = SimpleDocumentStore.from_persist_path(str(docstore_path))
            logger.info("Loaded existing document store for Parent-Child relationships.")
        except Exception as e:
            logger.warning(f"Could not load existing docstore: {e}. Initializing fresh docstore.")

    storage_context = StorageContext.from_defaults(
        vector_store=vector_store,
        docstore=docstore
    )

    # Read parsed markdown files
    md_files = list(docs_folder.glob("*.md"))
    if not md_files:
        logger.warning(f"No .md documents found in {docs_folder}. Returning existing or empty index.")
        index = VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context)
        return index, docstore

    logger.info(f"Loading {len(md_files)} markdown files from {docs_folder}...")
    reader = SimpleDirectoryReader(input_dir=str(docs_folder), required_exts=[".md"])
    documents = reader.load_data()

    # Tag documents with source metadata
    for doc in documents:
        doc.metadata["source_filename"] = Path(doc.metadata.get("file_path", "")).name

    nodes, leaf_nodes = build_hierarchical_nodes(documents)
    docstore.add_documents(nodes)
    docstore.persist(str(docstore_path))

    index = VectorStoreIndex(
        leaf_nodes,
        storage_context=storage_context,
        embed_model=embed_model,
        show_progress=True
    )
    logger.info("ChromaDB index build/update completed successfully.")
    return index, docstore

if __name__ == "__main__":
    logger.info("Running Phase 2 Indexing script...")
    idx, ds = build_index()
    logger.info("Indexing finished.")
