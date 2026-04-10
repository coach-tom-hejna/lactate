"""
Simple Bearer-token authentication.
Token is read from the API_KEY environment variable.
"""
from __future__ import annotations

import os
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

_bearer = HTTPBearer(auto_error=False)


def get_api_key() -> str:
    key = os.getenv("API_KEY", "").strip()
    if not key:
        raise RuntimeError("API_KEY environment variable is not set.")
    return key


def verify_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> str:
    """Validate Bearer token. Raises 401 if missing or wrong."""
    api_key = get_api_key()
    if credentials is None or credentials.credentials != api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials
