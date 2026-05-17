from __future__ import annotations

import argparse
import os
import sys

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from mcp_kanboard.client import KanboardClient
from mcp_kanboard.config import load_settings
from mcp_kanboard.tools import register_all


def _build(host: str = "127.0.0.1", port: int = 8765, disable_host_check: bool = False) -> FastMCP:
    settings = load_settings()
    client = KanboardClient(settings)
    kwargs: dict = {"host": host, "port": port}
    if disable_host_check:
        # In --http mode we sit behind a tunnel (e.g. ngrok) whose Host header is
        # not 127.0.0.1/localhost. Bearer auth replaces the DNS-rebinding guard.
        kwargs["transport_security"] = TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        )
    instance = FastMCP("kanboard", **kwargs)
    register_all(instance, client)
    return instance


_CANONICAL_ACCEPT = b"application/json, text/event-stream"


def _normalize_accept_asgi(app):
    """Force the Accept header to MCP's required value.

    FastMCP's streamable-http handler 406s any request whose Accept header
    doesn't include both 'application/json' and 'text/event-stream'. Some
    MCP clients (notably claude.ai's connector backend) send 'Accept: */*'
    and get rejected. MCP only ever returns those two content types, so
    rewriting the header is safe.
    """

    async def middleware(scope, receive, send):
        if scope["type"] != "http":
            await app(scope, receive, send)
            return
        raw_headers = list(scope.get("headers") or [])
        rewritten = [(k, v) for k, v in raw_headers if k.lower() != b"accept"]
        rewritten.append((b"accept", _CANONICAL_ACCEPT))
        scope = dict(scope)
        scope["headers"] = rewritten
        await app(scope, receive, send)

    return middleware


def _bearer_auth_asgi(app, token: str):
    expected = f"Bearer {token}".encode()

    async def middleware(scope, receive, send):
        if scope["type"] != "http":
            await app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        if headers.get(b"authorization", b"").strip() != expected:
            body = b'{"error":"unauthorized"}'
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode()),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return
        await app(scope, receive, send)

    return middleware


def main() -> None:
    parser = argparse.ArgumentParser(prog="mcp-kanboard")
    parser.add_argument(
        "--http",
        action="store_true",
        help="Run with streamable-http transport (for remote MCP clients like claude.ai). Default is stdio.",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("MCP_HTTP_HOST", "127.0.0.1"),
        help="Bind host for --http mode (default 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("MCP_HTTP_PORT", "8765")),
        help="Bind port for --http mode (default 8765).",
    )
    parser.add_argument(
        "--insecure-no-auth",
        action="store_true",
        help="Skip bearer-token check in --http mode. ONLY use behind a private tunnel.",
    )
    args = parser.parse_args()

    try:
        server = _build(host=args.host, port=args.port, disable_host_check=args.http)
    except RuntimeError as exc:
        print(f"[mcp-kanboard] startup failed: {exc}", file=sys.stderr)
        sys.exit(2)

    if not args.http:
        server.run()
        return

    import uvicorn

    app = server.streamable_http_app()
    app = _normalize_accept_asgi(app)
    path = server.settings.streamable_http_path

    if args.insecure_no_auth:
        print(
            "[mcp-kanboard] WARNING: --insecure-no-auth set; the HTTP endpoint has NO authentication.",
            file=sys.stderr,
        )
    else:
        token = os.environ.get("MCP_BEARER_TOKEN", "").strip()
        if not token:
            print(
                "[mcp-kanboard] MCP_BEARER_TOKEN env var is required in --http mode "
                "(or pass --insecure-no-auth to disable auth).",
                file=sys.stderr,
            )
            sys.exit(2)
        app = _bearer_auth_asgi(app, token)

    print(
        f"[mcp-kanboard] HTTP transport listening on http://{args.host}:{args.port}{path}",
        file=sys.stderr,
    )
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


try:
    mcp = _build()
except RuntimeError:
    mcp = None  # type: ignore[assignment]


if __name__ == "__main__":
    main()
