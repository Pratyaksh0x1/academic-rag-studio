import logging
from typing import List, Dict, Any, Optional

import config
from src.retrieval import retrieve_and_rerank, get_llm, RetrievalError, get_threshold
from src.llm_utils import complete_with_fallback, is_rate_limit_error

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("generation")


def fetch_tavily_web_results(query: str) -> List[Dict[str, str]]:
    if not config.TAVILY_API_KEY:
        logger.warning("TAVILY_API_KEY is missing. Skipping web fallback search.")
        return []
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=config.TAVILY_API_KEY)
        response = client.search(query=query, search_depth="advanced", max_results=5)
        results = []
        for res in response.get("results", []):
            results.append(
                {
                    "title": res.get("title", "Web Result"),
                    "url": res.get("url", ""),
                    "content": res.get("content", ""),
                }
            )
        logger.info("Tavily returned %s web search results.", len(results))
        return results
    except Exception as exc:
        logger.error("Error executing Tavily web search: %s", exc)
        return []


def calculate_confidence_score(chunks: List[Dict[str, Any]]) -> float:
    if not chunks:
        return 0.0
    scores = []
    for chunk in chunks:
        try:
            scores.append(min(1.0, max(0.0, float(chunk.get("score", 0.0)))))
        except (TypeError, ValueError):
            continue
    if not scores:
        return 0.0
    max_score = max(scores)
    avg_score = sum(scores) / len(scores)
    return round((max_score * 0.6) + (avg_score * 0.4), 4)


def _format_chunk_sources(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "filename": chunk["source_filename"],
            "score": chunk["score"],
            "text_snippet": chunk["text"][:300],
            "type": "document",
        }
        for chunk in chunks
    ]


def _generate_from_chunks(
    query: str,
    top_chunks: List[Dict[str, Any]],
    mode: str,
    *,
    low_confidence: bool = False,
) -> str:
    context_str = "\n\n".join(
        [f"[Source: {chunk['source_filename']}]\n{chunk['text']}" for chunk in top_chunks]
    )
    caveat = (
        "Note: retrieval confidence is moderate. Ground your answer strictly in the excerpts and "
        "state uncertainty where evidence is weak.\n\n"
        if low_confidence
        else ""
    )
    system_prompt = (
        "You are a rigorous academic research assistant. Answer the user question using ONLY "
        "the provided academic paper excerpts. Cite sources inline using [Filename.pdf]. "
        "If the context does not contain the answer, state that explicitly.\n\n"
        f"{caveat}"
        f"Context Excerpts:\n{context_str}\n\n"
        f"User Question: {query}\n\n"
        "Academic Response:"
    )
    llm = get_llm(mode)
    return complete_with_fallback(llm, system_prompt, mode=mode, label="answer generation")


def generate_answer(
    query: str,
    top_chunks: Optional[List[Dict[str, Any]]] = None,
    mode: str = None,
    threshold: float = None,
) -> Dict[str, Any]:
    mode = mode or config.config.mode
    threshold = threshold if threshold is not None else get_threshold(mode)
    retrieval_error = None

    if top_chunks is None:
        try:
            top_chunks = retrieve_and_rerank(query, mode=mode)
        except RetrievalError as exc:
            retrieval_error = str(exc)
            top_chunks = []

    confidence_score = calculate_confidence_score(top_chunks)
    logger.info(
        "Retrieval confidence for '%s': %.4f (threshold %.4f)",
        query,
        confidence_score,
        threshold,
    )

    generation_mode = "local_kb"
    sources: List[Dict[str, Any]] = []
    answer_text = ""
    warnings: List[str] = []

    if retrieval_error:
        warnings.append(retrieval_error)

    if top_chunks:
        sources = _format_chunk_sources(top_chunks)
        low_confidence = confidence_score < threshold
        try:
            answer_text = _generate_from_chunks(
                query,
                top_chunks,
                mode,
                low_confidence=low_confidence,
            )
            generation_mode = "local_kb_low_confidence" if low_confidence else "local_kb"
            if low_confidence:
                warnings.append(
                    "Retrieval confidence was below the preferred threshold, but an answer was "
                    "still generated from your indexed documents."
                )
        except Exception as exc:
            logger.error("LLM generation failed: %s", exc)
            if is_rate_limit_error(exc):
                warnings.append("Cloud API rate limit reached. Switch to local mode or retry later.")
            generation_mode = "generation_error"
            answer_text = (
                "Retrieved relevant document excerpts but answer generation failed. "
                "Review the source excerpts below."
            )
            warnings.append(str(exc))
    else:
        generation_mode = "web_fallback"
        logger.info("No document chunks retrieved. Attempting optional web fallback.")
        web_results = fetch_tavily_web_results(query)
        if web_results:
            web_context = "\n\n".join(
                [f"[Source: {item['title']} ({item['url']})]\n{item['content']}" for item in web_results]
            )
            prompt = (
                "You are an academic research assistant. Answer using the following web search results. "
                "Clearly label that the answer was sourced from live web search.\n\n"
                f"Web Results:\n{web_context}\n\n"
                f"User Question: {query}\n\n"
                "Response:"
            )
            try:
                answer_text = complete_with_fallback(get_llm(mode), prompt, mode=mode, label="web fallback")
                sources = [
                    {"title": item["title"], "url": item["url"], "snippet": item["content"][:200], "type": "web"}
                    for item in web_results
                ]
            except Exception as exc:
                answer_text = "Web fallback failed and no indexed documents matched your query."
                warnings.append(str(exc))
        else:
            answer_text = (
                "No matching content was found in your indexed PDFs. "
                "Upload documents and run indexing, then try again."
            )
            if retrieval_error:
                answer_text = retrieval_error

    return {
        "query": query,
        "answer": answer_text,
        "mode": generation_mode,
        "confidence_score": confidence_score,
        "sources": sources,
        "retrieved_chunks": top_chunks,
        "warnings": warnings,
    }


if __name__ == "__main__":
    question = "Explain the multi-head attention mechanism formulation."
    logger.info("Testing generation for query: %s", question)
    result = generate_answer(question)
    logger.info("Mode: %s | Confidence: %s", result["mode"], result["confidence_score"])
    logger.info("Answer snippet: %s...", result["answer"][:300])
