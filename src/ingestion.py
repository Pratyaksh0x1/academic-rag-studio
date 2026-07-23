import os
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ingestion")

def parse_with_llama_parse(pdf_path: Path) -> str:
    """Parses a PDF using LlamaParse SDK to extract Markdown with preserved tables and LaTeX."""
    if not config.LLAMA_CLOUD_API_KEY:
        raise ValueError("LLAMA_CLOUD_API_KEY not found in environment variables.")
    
    from llama_parse import LlamaParse
    
    parser = LlamaParse(
        api_key=config.LLAMA_CLOUD_API_KEY,
        result_type="markdown",
        verbose=True,
        language="en"
    )
    
    documents = parser.load_data(str(pdf_path))
    parsed_text = "\n\n".join([doc.get_content() for doc in documents])
    return parsed_text

def parse_with_unstructured_fallback(pdf_path: Path) -> str:
    """Fallback PDF parsing using unstructured library."""
    logger.warning(f"Using fallback unstructured parser for {pdf_path.name}")
    try:
        from unstructured.partition.pdf import partition_pdf
        elements = partition_pdf(filename=str(pdf_path))
        text = "\n\n".join([str(el) for el in elements])
        return text
    except Exception as e:
        logger.error(f"Fallback unstructured parsing failed for {pdf_path.name}: {e}")
        # Last resort basic fallback using PyPDF2 or pypdf if available
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(pdf_path))
            pages_text = [page.extract_text() for page in reader.pages if page.extract_text()]
            return "\n\n".join(pages_text)
        except Exception as pypdf_err:
            logger.error(f"PyPDF fallback also failed: {pypdf_err}")
            raise e

def parse_pdf(pdf_path: Path, output_dir: Path = config.OUTPUT_DIR) -> Dict[str, Any]:
    """
    Parses a single PDF file, attempts LlamaParse first, falls back to unstructured/pypdf.
    Saves parsed result as .md file in output_dir.
    Returns metrics dict.
    """
    start_time = time.time()
    pdf_path = Path(pdf_path)
    output_filename = pdf_path.stem + ".md"
    output_path = output_dir / output_filename
    
    parsed_text = ""
    parse_method = "LlamaParse"
    
    try:
        if config.LLAMA_CLOUD_API_KEY:
            logger.info(f"Starting LlamaParse for {pdf_path.name}...")
            parsed_text = parse_with_llama_parse(pdf_path)
        else:
            logger.warning("LLAMA_CLOUD_API_KEY missing, jumping to fallback parser.")
            parsed_text = parse_with_unstructured_fallback(pdf_path)
            parse_method = "Fallback (Unstructured/PyPDF)"
    except Exception as err:
        logger.error(f"LlamaParse encountered error: {err}. Attempting fallback...")
        try:
            parsed_text = parse_with_unstructured_fallback(pdf_path)
            parse_method = "Fallback (Unstructured/PyPDF)"
        except Exception as final_err:
            logger.critical(f"All parsing methods failed for {pdf_path.name}: {final_err}")
            raise final_err
            
    elapsed_time = round(time.time() - start_time, 2)
    char_count = len(parsed_text)
    
    # Save markdown file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(parsed_text)
        
    logger.info(f"Parsed {pdf_path.name} via {parse_method} -> {output_filename} ({char_count} chars, {elapsed_time}s)")
    
    return {
        "source_pdf": str(pdf_path),
        "output_md": str(output_path),
        "char_count": char_count,
        "elapsed_seconds": elapsed_time,
        "method": parse_method
    }

def process_pdf_folder(docs_folder: Path = config.DATA_DIR, output_dir: Path = config.OUTPUT_DIR) -> List[Dict[str, Any]]:
    """
    Parses all PDFs in input folder and writes .md files to output_dir.
    """
    docs_folder = Path(docs_folder)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    pdf_files = list(docs_folder.glob("*.pdf"))
    if not pdf_files:
        logger.warning(f"No PDF files found in {docs_folder}")
        return []
        
    results = []
    for pdf_path in pdf_files:
        try:
            res = parse_pdf(pdf_path, output_dir)
            results.append(res)
        except Exception as e:
            logger.error(f"Failed to process {pdf_path.name}: {e}")
            
    return results

if __name__ == "__main__":
    import sys
    folder = sys.argv[1] if len(sys.argv) > 1 else config.DATA_DIR
    logger.info(f"Running ingestion on folder: {folder}")
    summary = process_pdf_folder(folder)
    logger.info(f"Ingestion complete. Processed {len(summary)} files.")
