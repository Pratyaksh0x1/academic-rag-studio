import logging
from typing import Dict, List, Optional, Any
import pymongo
from pymongo import MongoClient
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("database")

class MongoDBHandler:
    def __init__(self, uri: str = config.MONGODB_URI):
        self.uri = uri
        try:
            self.client = MongoClient(self.uri, serverSelectionTimeoutMS=2000)
            self.db = self.client["academic_rag_db"]
            self.users = self.db["users"]
            self.chat_history = self.db["chat_history"]
            logger.info("Connected to MongoDB successfully.")
        except Exception as e:
            logger.warning(f"Could not connect to MongoDB at {uri}: {e}. Running in memory fallback mode.")
            self.client = None
            self.db = None
            self.users = None
            self.chat_history = None

    def create_user(self, username: str, password_hash: str) -> bool:
        if self.users is None:
            return True
        if self.users.find_one({"username": username}):
            return False
        self.users.insert_one({"username": username, "password_hash": password_hash})
        return True

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        if self.users is None:
            return None
        return self.users.find_one({"username": username})

    def save_chat(self, username: str, query: str, answer: str, sources: List[Dict[str, Any]], mode: str):
        if self.chat_history is None:
            return
        self.chat_history.insert_one({
            "username": username,
            "query": query,
            "answer": answer,
            "sources": sources,
            "mode": mode
        })

    def get_user_chat_history(self, username: str) -> List[Dict[str, Any]]:
        if self.chat_history is None:
            return []
        cursor = self.chat_history.find({"username": username}, {"_id": 0})
        return list(cursor)

db_handler = MongoDBHandler()
