import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unittest
import config
from src.generation import calculate_confidence_score
from src.retrieval import generate_sub_queries

class TestAcademicRAGPipeline(unittest.TestCase):
    def test_config_initialization(self):
        self.assertIn(config.config.mode, ["local", "cloud"])
        config.config.set_mode("local")
        self.assertTrue(config.config.is_local)
        
    def test_confidence_score_calculation(self):
        sample_chunks = [
            {"score": 0.85, "text": "sample text 1"},
            {"score": 0.75, "text": "sample text 2"}
        ]
        score = calculate_confidence_score(sample_chunks)
        self.assertGreater(score, 0.5)
        
    def test_sub_query_generation_fallback(self):
        # Fallback test
        sub_queries = generate_sub_queries("What is transformer attention?")
        self.assertIsInstance(sub_queries, list)
        self.assertGreater(len(sub_queries), 0)

if __name__ == "__main__":
    unittest.main()
