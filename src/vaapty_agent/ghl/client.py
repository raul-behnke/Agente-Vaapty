"""Cliente HTTP async para a API GoHighLevel, com retry e tratamento de erro."""
from __future__ import annotations

import time
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from ..config import settings
from ..logging import get_logger
from ..metrics import GHL_LATENCY

log = get_logger("ghl.client")

# UA de browser: Cloudflare (erro 1010) bloqueia o User-Agent padrão de libs.
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


class GHLError(Exception):
    def __init__(self, message: str, status_code: int | None = None, body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, GHLError):
        if exc.status_code in _RETRYABLE_STATUS:
            return True
        # quirk GHL: 401 com "timed out" no corpo é transitório
        if exc.status_code == 401 and isinstance(exc.body, dict):
            msg = str(exc.body.get("message", "")).lower()
            return "timed out" in msg
    return False


class GHLClient:
    def __init__(self) -> None:
        self._http = httpx.AsyncClient(
            base_url=settings.ghl_api_host.rstrip("/"),
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {settings.ghl_pit_token}",
                "Version": settings.ghl_api_version,
                "Accept": "application/json",
                "User-Agent": _USER_AGENT,
            },
        )

    async def close(self) -> None:
        await self._http.aclose()

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        reraise=True,
    )
    async def _request(
        self, method: str, path: str, *, operation: str, json: Any = None, params: Any = None
    ) -> dict:
        t0 = time.perf_counter()
        try:
            resp = await self._http.request(method, path, json=json, params=params)
        finally:
            GHL_LATENCY.labels(operation=operation).observe(time.perf_counter() - t0)

        if resp.status_code == 204 or not resp.content:
            return {}
        try:
            body = resp.json()
        except Exception:
            body = {"raw": resp.text}
        if resp.status_code >= 400:
            raise GHLError(
                f"GHL {operation} {resp.status_code}", status_code=resp.status_code, body=body
            )
        return body

    async def get(self, path: str, *, operation: str, params: Any = None) -> dict:
        return await self._request("GET", path, operation=operation, params=params)

    async def post(self, path: str, *, operation: str, json: Any = None) -> dict:
        return await self._request("POST", path, operation=operation, json=json)

    async def put(self, path: str, *, operation: str, json: Any = None) -> dict:
        return await self._request("PUT", path, operation=operation, json=json)

    async def delete(self, path: str, *, operation: str, json: Any = None) -> dict:
        return await self._request("DELETE", path, operation=operation, json=json)


_client: GHLClient | None = None


def get_client() -> GHLClient:
    global _client
    if _client is None:
        _client = GHLClient()
    return _client


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None
