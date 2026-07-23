"""Lightweight local user store for the Streamlit app.

Provides real (persisted, hashed) authentication instead of a session-only
accept-anything login. Users are stored as a JSON file on disk so accounts
survive across server restarts. Passwords are never stored in plain text.
"""

import hashlib
import json
import re
import secrets
from pathlib import Path
from typing import Optional

import config

USERS_FILE = config.BASE_DIR / "users.json"
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]{3,32}$")


def _load() -> dict:
    if not USERS_FILE.exists():
        return {}
    try:
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save(users: dict) -> None:
    USERS_FILE.write_text(json.dumps(users, indent=2), encoding="utf-8")


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}{password}".encode("utf-8")).hexdigest()


def validate_username(username: str) -> Optional[str]:
    if not USERNAME_PATTERN.match(username):
        return "Username must be 3-32 characters (letters, numbers, '.', '_', '-')."
    return None


def validate_password(password: str) -> Optional[str]:
    if len(password) < 8:
        return "Password must be at least 8 characters long."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"[0-9]", password):
        return "Password must include at least one letter and one number."
    return None


def user_exists(username: str) -> bool:
    return username.lower() in _load()


def create_user(username: str, password: str, display_name: str = "") -> None:
    users = _load()
    salt = secrets.token_hex(16)
    users[username.lower()] = {
        "username": username,
        "display_name": display_name or username,
        "salt": salt,
        "password_hash": _hash_password(password, salt),
    }
    _save(users)


def verify_user(username: str, password: str) -> Optional[dict]:
    users = _load()
    record = users.get(username.lower())
    if not record:
        return None
    if _hash_password(password, record["salt"]) != record["password_hash"]:
        return None
    return record
