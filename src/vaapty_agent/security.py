"""Auth do webhook: shared-secret no query param ?secret= (compare_digest)."""
from __future__ import annotations

import hmac

from fastapi import HTTPException, Query, status

from .config import settings


def require_secret(secret: str = Query(...)) -> None:
    if not hmac.compare_digest(secret, settings.webhook_secret):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid secret")
