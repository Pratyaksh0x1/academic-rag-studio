import time
from typing import Optional
import bcrypt
import jwt
from fastapi import HTTPException, Security, status, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import config

security = HTTPBearer(auto_error=not config.DISABLE_AUTH)


def hash_password(password: str) -> str:
    """Salted bcrypt hash. Each call produces a different hash for the same
    password (bcrypt generates a fresh random salt internally), so hashes
    must be compared with verify_password(), never with `==`."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        # Handles legacy/malformed hashes (e.g. old sha256 hex digests) gracefully
        # instead of raising, so a bad stored hash just fails auth rather than 500s.
        return False


def create_jwt_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": time.time() + 86400,
    }
    return jwt.encode(payload, config.JWT_SECRET_KEY, algorithm="HS256")


def verify_jwt_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> str:
    if config.DISABLE_AUTH:
        return "guest"

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required.",
        )

    token = credentials.credentials
    try:
        payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=["HS256"])
        return payload.get("sub", "anonymous")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization token.")


def optional_user(username: str = Depends(verify_jwt_token)) -> str:
    return username
