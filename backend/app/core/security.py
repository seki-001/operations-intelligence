"""Simple shared-key auth for server-to-server calls from the dashboard.

The key lives only on the servers (backend env + Next.js server env); it is never
sent to the browser. In production a missing key is a hard failure, not a bypass.
"""

import secrets

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not settings.api_key:
        if settings.environment == "production":
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "API key not configured")
        return  # local development without a key
    if not x_api_key or not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing API key")
