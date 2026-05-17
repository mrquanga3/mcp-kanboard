from __future__ import annotations

import time
import uuid
from typing import Any

import httpx

from mcp_kanboard.config import Settings
from mcp_kanboard.errors import AuthError, KanboardError, NotFoundError

_GET_BY_ID_PREFIXES = ("get",)
_RETRYABLE_EXC = (httpx.TransportError, httpx.ReadTimeout)


class KanboardClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._http = httpx.Client(
            auth=(settings.username, settings.api_token),
            timeout=settings.timeout_seconds,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            verify=settings.verify_ssl,
        )

    @property
    def settings(self) -> Settings:
        return self._settings

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "KanboardClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def call(self, method: str, params: dict[str, Any] | list[Any] | None = None) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "id": uuid.uuid4().int >> 96,
            "method": method,
        }
        if params is not None:
            payload["params"] = params

        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                response = self._http.post(self._settings.url, json=payload)
                break
            except _RETRYABLE_EXC as exc:
                last_exc = exc
                if attempt == 2:
                    raise KanboardError(f"Network error calling Kanboard: {exc}") from exc
                time.sleep(0.5 * (attempt + 1))
        else:  # pragma: no cover
            raise KanboardError(f"Network error calling Kanboard: {last_exc}")

        if response.status_code in (401, 403):
            raise AuthError(
                "Kanboard authentication failed. Check KANBOARD_USERNAME "
                "(must be 'jsonrpc' for an Application token, or your login for a Personal token) "
                "and KANBOARD_API_TOKEN."
            )
        if response.status_code >= 500:
            snippet = response.text[:500]
            raise KanboardError(f"Kanboard server error {response.status_code}: {snippet}")
        if response.status_code >= 400:
            snippet = response.text[:500]
            raise KanboardError(f"Kanboard HTTP {response.status_code}: {snippet}")

        try:
            body = response.json()
        except ValueError as exc:
            raise KanboardError(f"Non-JSON response from Kanboard: {response.text[:300]!r}") from exc

        if isinstance(body, dict) and "error" in body:
            err = body["error"]
            code = err.get("code") if isinstance(err, dict) else None
            message = err.get("message") if isinstance(err, dict) else str(err)
            data = err.get("data") if isinstance(err, dict) else None
            if code == -32601:
                raise KanboardError(f"Unknown Kanboard method: {method}")
            detail = f" ({data})" if data else ""
            raise KanboardError(f"Kanboard error: {message}{detail}")

        result = body.get("result") if isinstance(body, dict) else None

        if result is False or result is None:
            if method.startswith(_GET_BY_ID_PREFIXES) and "ById" in method or method in {"getMe"}:
                raise NotFoundError(f"Kanboard returned no record for {method} with params={params!r}")
            if _is_mutating(method) and result is False:
                raise KanboardError(
                    f"Kanboard refused operation {method} (check params, permissions, or duplicates)."
                )
        return result


def _is_mutating(method: str) -> bool:
    return method.startswith(("create", "update", "remove", "move", "set", "enable", "disable", "open", "close", "duplicate", "change", "add"))
