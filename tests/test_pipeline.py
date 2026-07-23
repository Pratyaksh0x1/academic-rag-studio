import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unittest
import config
from src.generation import calculate_confidence_score, generate_answer
from src.indexing import validate_index_mode, embedding_model_name
from src.llm_utils import is_rate_limit_error
from src.retrieval import generate_sub_queries


class TestAcademicRAGPipeline(unittest.TestCase):
    def test_config_initialization(self):
        self.assertIn(config.config.mode, ["local", "cloud"])
        config.config.set_mode("local")
        self.assertTrue(config.config.is_local)

    def test_confidence_score_calculation(self):
        sample_chunks = [
            {"score": 0.85, "text": "sample text 1"},
            {"score": 0.75, "text": "sample text 2"},
        ]
        score = calculate_confidence_score(sample_chunks)
        self.assertGreater(score, 0.5)

    def test_mode_specific_thresholds(self):
        self.assertLess(config.confidence_threshold_for_mode("local"), config.confidence_threshold_for_mode("cloud"))

    def test_rate_limit_detection(self):
        self.assertTrue(is_rate_limit_error(Exception("Error 429: rate limit exceeded")))
        self.assertFalse(is_rate_limit_error(Exception("connection refused")))

    def test_validate_index_mode_without_metadata(self):
        compatible, _ = validate_index_mode("local")
        self.assertTrue(compatible)

    def test_embedding_model_name_local(self):
        config.config.set_mode("local")
        self.assertEqual(embedding_model_name("local"), config.LOCAL_EMBEDDING_MODEL)

    def test_sub_query_generation_fallback(self):
        sub_queries = generate_sub_queries("What is transformer attention?")
        self.assertIsInstance(sub_queries, list)
        self.assertGreater(len(sub_queries), 0)

    def test_generate_answer_returns_chunks_key(self):
        result = generate_answer("test query", top_chunks=[], mode="local")
        self.assertIn("retrieved_chunks", result)
        self.assertIn("warnings", result)


if __name__ == "__main__":
    unittest.main()
