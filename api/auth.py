import hashlib
import time
from typing import Optional
import jwt
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import config

security = HTTPBearer()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def create_jwt_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": time.time() + 86400 # 24 hour expiry
    }
    return jwt.encode(payload, config.JWT_SECRET_KEY, algorithm="HS256")

def verify_jwt_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=["HS256"])
        return payload.get("sub", "anonymous")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization token.")
