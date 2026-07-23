import logging
from pathlib import Path
from typing import List, Tuple, Any, Optional
import chromadb

from llama_index.core import SimpleDirectoryReader, StorageContext, VectorStoreIndex, Document
from llama_index.core.node_parser import HierarchicalNodeParser, get_leaf_nodes, get_root_nodes
from llama_index.core.storage.docstore import SimpleDocumentStore
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
            effective_mode = "local"
        else:
            logger.info("Using Cloud OpenAI Embedding model: %s", config.CLOUD_EMBEDDING_MODEL)
            model = OpenAIEmbedding(model=config.CLOUD_EMBEDDING_MODEL, api_key=config.OPENAI_API_KEY)
            effective_mode = "cloud"
    else:
        logger.info("Using Local HuggingFace Embedding model: %s", config.LOCAL_EMBEDDING_MODEL)
        model = HuggingFaceEmbedding(model_name=config.LOCAL_EMBEDDING_MODEL)
        effective_mode = "local"

    _EMBED_MODEL_CACHE[mode] = model
    _EMBED_MODEL_CACHE[effective_mode] = model
    return model


def embedding_model_name(mode: str = None) -> str:
    mode = mode or config.config.mode
    if mode == "cloud" and config.OPENAI_API_KEY:
        return config.CLOUD_EMBEDDING_MODEL
    return config.LOCAL_EMBEDDING_MODEL


def validate_index_mode(mode: str = None) -> Tuple[bool, str]:
    """Ensure query embedding mode matches the indexed vectors."""
    mode = mode or config.config.mode
    meta = config.load_index_metadata()
    if not meta:
        return True, "No index metadata found; assuming compatible index."

    indexed_mode = meta.get("embedding_mode", "local")
    indexed_model = meta.get("embedding_model", config.LOCAL_EMBEDDING_MODEL)
    current_model = embedding_model_name(mode)

    if indexed_mode != mode or indexed_model != current_model:
        return False, (
            f"Index was built in '{indexed_mode}' mode ({indexed_model}) but you are querying in "
            f"'{mode}' mode ({current_model}). Re-index your documents in the current mode."
        )
    return True, "Index mode compatible."


def get_index_stats(persist_dir: Path = config.CHROMADB_DIR) -> dict:
    persist_dir = Path(persist_dir)
    meta = config.load_index_metadata()
    vector_count = 0
    try:
        db = chromadb.PersistentClient(path=str(persist_dir))
        collection = db.get_or_create_collection(config.COLLECTION_NAME)
        vector_count = collection.count()
    except Exception as exc:
        logger.warning("Could not read Chroma collection stats: %s", exc)

    md_files = sorted(p.name for p in config.OUTPUT_DIR.glob("*.md"))
    return {
        "vector_count": vector_count,
        "document_count": len(md_files),
        "documents": md_files,
        "embedding_mode": meta.get("embedding_mode", "unknown"),
        "embedding_model": meta.get("embedding_model", "unknown"),
        "indexed_files": meta.get("indexed_files", []),
    }


def build_hierarchical_nodes(documents: List[Document]) -> Tuple[List[Any], List[Any]]:
    node_parser = HierarchicalNodeParser.from_defaults(
        chunk_sizes=[config.PARENT_CHUNK_SIZE, config.CHILD_CHUNK_SIZE],
        chunk_overlap=config.CHUNK_OVERLAP,
    )
    nodes = node_parser.get_nodes_from_documents(documents)
    leaf_nodes = get_leaf_nodes(nodes)
    root_nodes = get_root_nodes(nodes)
    logger.info(
        "Generated %s total nodes: %s parent nodes, %s leaf nodes.",
        len(nodes),
        len(root_nodes),
        len(leaf_nodes),
    )
    return nodes, leaf_nodes


def build_index(
    docs_folder: Path = config.OUTPUT_DIR,
    persist_dir: Path = config.CHROMADB_DIR,
    collection_name: str = config.COLLECTION_NAME,
    mode: str = None,
    rebuild: bool = False,
) -> Tuple[VectorStoreIndex, SimpleDocumentStore]:
    docs_folder = Path(docs_folder)
    persist_dir = Path(persist_dir)
    persist_dir.mkdir(parents=True, exist_ok=True)
    mode = mode or config.config.mode

    embed_model = get_embedding_model(mode)
    Settings.embed_model = embed_model

    db = chromadb.PersistentClient(path=str(persist_dir))
    if rebuild:
        try:
            db.delete_collection(collection_name)
        except Exception:
            pass
    chroma_collection = db.get_or_create_collection(collection_name)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

    docstore_path = persist_dir / "docstore.json"
    docstore = SimpleDocumentStore()
    if docstore_path.exists() and not rebuild:
        try:
            docstore = SimpleDocumentStore.from_persist_path(str(docstore_path))
            logger.info("Loaded existing document store for parent-child relationships.")
        except Exception as exc:
            logger.warning("Could not load existing docstore: %s. Starting fresh.", exc)

    storage_context = StorageContext.from_defaults(
        vector_store=vector_store,
        docstore=docstore,
    )

    md_files = list(docs_folder.glob("*.md"))
    if not md_files:
        logger.warning("No .md documents found in %s.", docs_folder)
        index = VectorStoreIndex.from_vector_store(
            vector_store=vector_store,
            storage_context=storage_context,
            embed_model=embed_model,
        )
        return index, docstore

    meta = config.load_index_metadata()
    already_indexed = set(meta.get("indexed_files", []))
    new_files = [f for f in md_files if f.name not in already_indexed] if not rebuild else md_files

    if not new_files and not rebuild:
        logger.info("All markdown files already indexed. Skipping re-embedding.")
        index = VectorStoreIndex.from_vector_store(
            vector_store=vector_store,
            storage_context=storage_context,
            embed_model=embed_model,
        )
        return index, docstore

    files_to_load = new_files if not rebuild else md_files
    logger.info("Indexing %s markdown file(s)...", len(files_to_load))

    documents: List[Document] = []
    for md_path in files_to_load:
        reader = SimpleDirectoryReader(input_files=[str(md_path)])
        loaded = reader.load_data()
        for doc in loaded:
            doc.metadata["source_filename"] = md_path.name
            doc.metadata["file_path"] = str(md_path)
        documents.extend(loaded)

    nodes, leaf_nodes = build_hierarchical_nodes(documents)
    docstore.add_documents(nodes)
    docstore.persist(str(docstore_path))

    index = VectorStoreIndex(
        leaf_nodes,
        storage_context=storage_context,
        embed_model=embed_model,
        show_progress=True,
    )

    indexed_names = sorted(set(already_indexed) | {f.name for f in files_to_load})
    config.save_index_metadata(
        {
            "embedding_mode": mode if mode == "cloud" and config.OPENAI_API_KEY else "local",
            "embedding_model": embedding_model_name(mode),
            "indexed_files": indexed_names,
            "vector_count": chroma_collection.count(),
            "parent_chunk_size": config.PARENT_CHUNK_SIZE,
            "child_chunk_size": config.CHILD_CHUNK_SIZE,
        }
    )
    logger.info("ChromaDB index build completed successfully.")
    return index, docstore


if __name__ == "__main__":
    logger.info("Running indexing script...")
    build_index()
    logger.info("Indexing finished.")
