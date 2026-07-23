import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd

import config
from src.retrieval import get_llm

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("comparative_matrix")

EXTRACTION_PROMPT = """
Analyze the following academic paper text and extract key metadata:
1. Core Methodology: Brief summary of proposed technique/architecture.
2. Dataset Used: Benchmarks or datasets evaluated.
3. Key Findings: Main results or improvements achieved.
4. Limitations: Stated or implicit weaknesses/drawbacks.

Return strictly a raw valid JSON object with no markdown backticks or explanations:
{{
  "methodology": "...",
  "dataset": "...",
  "key_findings": "...",
  "limitations": "..."
}}

Paper Excerpt:
{text_sample}
"""

def extract_paper_metadata(file_path: Path, mode: str = None) -> Dict[str, str]:
    """Extracts methodology, dataset, findings, and limitations from a single parsed markdown paper."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Use first 3000 chars (intro, abstract, method) for summary extraction
    sample = content[:3500]
    llm = get_llm(mode)
    prompt = EXTRACTION_PROMPT.format(text_sample=sample)
    
    try:
        response = llm.complete(prompt)
        raw_text = response.text.strip()
        # Clean JSON markdown if enclosed
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        raw_text = raw_text.strip()
        
        parsed = json.loads(raw_text)
        return {
            "Paper Title / File": file_path.stem,
            "Core Methodology": parsed.get("methodology", "N/A"),
            "Dataset Used": parsed.get("dataset", "N/A"),
            "Key Findings": parsed.get("key_findings", "N/A"),
            "Limitations": parsed.get("limitations", "N/A")
        }
    except Exception as e:
        logger.error(f"Error extracting metadata for {file_path.name}: {e}")
        return {
            "Paper Title / File": file_path.stem,
            "Core Methodology": "Extraction failed",
            "Dataset Used": "Extraction failed",
            "Key Findings": "Extraction failed",
            "Limitations": "Extraction failed"
        }

def build_comparative_matrix(
    docs_folder: Path = config.OUTPUT_DIR,
    file_list: Optional[List[str]] = None,
    mode: str = None
) -> Dict[str, Any]:
    """
    Batch processes documents in output folder and builds comparative Pandas DataFrame,
    markdown string, and HTML string.
    """
    docs_folder = Path(docs_folder)
    if file_list:
        md_files = [docs_folder / f if not f.endswith(".md") else docs_folder / f for f in file_list]
        md_files = [f for f in md_files if f.exists()]
    else:
        md_files = list(docs_folder.glob("*.md"))
        
    if not md_files:
        logger.warning(f"No markdown files found in {docs_folder} for matrix generation.")
        df_empty = pd.DataFrame(columns=["Paper Title / File", "Core Methodology", "Dataset Used", "Key Findings", "Limitations"])
        return {
            "dataframe": df_empty,
            "markdown_table": "No papers available to compare.",
            "html_table": "<p>No papers available to compare.</p>"
        }
        
    logger.info(f"Generating comparative matrix across {len(md_files)} papers...")
    records = []
    for f_path in md_files:
        meta = extract_paper_metadata(f_path, mode=mode)
        records.append(meta)
        
    df = pd.DataFrame(records)
    md_table = df.to_markdown(index=False)
    html_table = df.to_html(index=False, classes="table table-striped table-bordered")
    
    return {
        "dataframe": df,
        "markdown_table": md_table,
        "html_table": html_table
    }

if __name__ == "__main__":
    logger.info("Running comparative matrix test...")
    res = build_comparative_matrix()
    logger.info(f"Matrix Markdown Table:\n\n{res['markdown_table']}")
