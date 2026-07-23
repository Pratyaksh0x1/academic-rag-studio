import logging
from typing import List, Dict, Tuple, Optional, Any
import config
from src.retrieval import retrieve_and_rerank, get_llm

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("generation")

def fetch_tavily_web_results(query: str) -> List[Dict[str, str]]:
    """Calls Tavily search API for web fallback when local KB confidence is low."""
    if not config.TAVILY_API_KEY:
        logger.warning("TAVILY_API_KEY is missing. Skipping live web fallback search.")
        return []
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=config.TAVILY_API_KEY)
        response = client.search(query=query, search_depth="advanced", max_results=5)
        results = []
        for res in response.get("results", []):
            results.append({
                "title": res.get("title", "Web Result"),
                "url": res.get("url", ""),
                "content": res.get("content", "")
            })
        logger.info(f"Tavily returned {len(results)} web search results.")
        return results
    except Exception as e:
        logger.error(f"Error executing Tavily web search: {e}")
        return []

def calculate_confidence_score(chunks: List[Dict[str, Any]]) -> float:
    """Calculates retrieval confidence score based on reranker similarity scores."""
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
    # Combination of top score and average score
    max_score = max(scores) if scores else 0.0
    avg_score = sum(scores) / len(scores) if scores else 0.0
    confidence = round((max_score * 0.6) + (avg_score * 0.4), 4)
    return confidence

def generate_answer(
    query: str,
    top_chunks: Optional[List[Dict[str, Any]]] = None,
    mode: str = None,
    threshold: float = config.CONFIDENCE_THRESHOLD
) -> Dict[str, Any]:
    """
    Core Phase 4 Generation & CRAG flow:
    1. Retrieve and rerank chunks if not provided
    2. Compute confidence score
    3. High confidence -> Local KB answer generation with citations
    4. Low confidence -> Fall back to Tavily web search
    """
    if top_chunks is None:
        top_chunks = retrieve_and_rerank(query, mode=mode)
        
    confidence_score = calculate_confidence_score(top_chunks)
    logger.info(f"Retrieval confidence score for '{query}': {confidence_score:.4f} (Threshold: {threshold})")
    
    llm = get_llm(mode)
    
    # Check if confidence threshold is satisfied
    if confidence_score >= threshold and top_chunks:
        generation_mode = "local_kb"
        context_str = "\n\n".join([
            f"[Source: {c['source_filename']}]\n{c['text']}"
            for c in top_chunks
        ])
        
        system_prompt = (
            "You are a rigorous academic researcher assistant. Answer the user question using ONLY "
            "the provided academic paper excerpts. Cite your sources inline using [Filename.pdf]. "
            "If the context does not contain the answer, state that explicitly.\n\n"
            f"Context Excerpts:\n{context_str}\n\n"
            f"User Question: {query}\n\n"
            "Academic Response:"
        )
        
        try:
            response = llm.complete(system_prompt)
            answer_text = response.text.strip()
        except Exception as e:
            logger.error(f"Error during LLM generation: {e}")
            answer_text = "An error occurred while generating the answer from the document context."
            
        sources = [
            {"filename": c["source_filename"], "score": c["score"], "text_snippet": c["text"][:200]}
            for c in top_chunks
        ]
    else:
        # Corrective RAG (CRAG) Fallback to Web Search
        generation_mode = "web_fallback"
        logger.info(f"Confidence score ({confidence_score:.4f}) below threshold ({threshold}). Triggering Tavily web fallback...")
        
        web_results = fetch_tavily_web_results(query)
        if web_results:
            web_context_str = "\n\n".join([
                f"[Source: {w['title']} ({w['url']})]\n{w['content']}"
                for w in web_results
            ])
            system_prompt = (
                "You are an academic research assistant. The local knowledge base did not yield sufficient "
                "confidence for this question. Answer the query using the following live web search results. "
                "Clearly label in your answer that it was 'sourced from live web search'.\n\n"
                f"Web Results:\n{web_context_str}\n\n"
                f"User Question: {query}\n\n"
                "Response:"
            )
            try:
                response = llm.complete(system_prompt)
                answer_text = response.text.strip()
            except Exception as e:
                logger.error(f"Error during web fallback LLM generation: {e}")
                answer_text = "Web search fallback returned results, but LLM generation failed."
            sources = [{"title": w["title"], "url": w["url"], "snippet": w["content"][:200]} for w in web_results]
        else:
            answer_text = (
                "The local knowledge base confidence was low, and live web search did not return results. "
                "Please refine your query or upload relevant academic PDFs."
            )
            sources = []
            
    return {
        "query": query,
        "answer": answer_text,
        "mode": generation_mode,
        "confidence_score": confidence_score,
        "sources": sources
    }

if __name__ == "__main__":
    q = "Explain the multi-head attention mechanism formulation."
    logger.info(f"Testing generation for query: {q}")
    res = generate_answer(q)
    logger.info(f"Mode: {res['mode']} | Confidence: {res['confidence_score']}")
    logger.info(f"Answer snippet: {res['answer'][:300]}...")
