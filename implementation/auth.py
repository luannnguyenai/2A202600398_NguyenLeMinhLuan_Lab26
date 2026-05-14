from __future__ import annotations

import json
from typing import Awaitable, Callable, Dict, List, Optional, Tuple

from starlette.middleware import Middleware


Headers = List[Tuple[bytes, bytes]]
Receive = Callable[[], Awaitable[Dict]]
Send = Callable[[Dict], Awaitable[None]]
Scope = Dict


class BearerTokenMiddleware:
    """Small ASGI middleware for demo HTTP/SSE bearer-token authentication."""

    def __init__(self, app: Callable, token: str):
        self.app = app
        self.token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        auth_header = self._header(scope.get("headers", []), b"authorization")
        if not auth_header:
            await self._json_error(send, 401, "Missing bearer token")
            return

        expected = f"Bearer {self.token}".encode()
        if auth_header != expected:
            await self._json_error(send, 403, "Invalid bearer token")
            return

        await self.app(scope, receive, send)

    @staticmethod
    def _header(headers: Headers, name: bytes) -> Optional[bytes]:
        for key, value in headers:
            if key.lower() == name:
                return value
        return None

    @staticmethod
    async def _json_error(send: Send, status_code: int, message: str) -> None:
        body = json.dumps({"ok": False, "error": message}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": status_code,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    (b"www-authenticate", b"Bearer"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


def auth_middleware(token: Optional[str]) -> List[Middleware]:
    """Return Starlette middleware for HTTP/SSE auth when a token is configured."""
    if not token:
        return []
    return [Middleware(BearerTokenMiddleware, token=token)]
