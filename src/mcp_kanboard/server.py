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
        # not 127.0.0.1/localhost. OAuth bearer auth (or --insecure-no-auth)
        # replaces the DNS-rebinding guard.
        kwargs["transport_security"] = TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        )
    instance = FastMCP("kanboard", **kwargs)
    register_all(instance, client)
    return instance


_CANONICAL_ACCEPT = b"application/json, text/event-stream"


def _normalize_accept_asgi(app):
    """Force Accept to MCP's required value.

    Some clients (claude.ai backend) send 'Accept: */*' and FastMCP 406s them
    because the streamable-http handler insists on both 'application/json' and
    'text/event-stream'. MCP only ever responds with those, so the rewrite is
    semantically safe.
    """

    async def middleware(scope, receive, send):
        if scope["type"] != "http":
            await app(scope, receive, send)
            return
        rewritten = [(k, v) for k, v in (scope.get("headers") or []) if k.lower() != b"accept"]
        rewritten.append((b"accept", _CANONICAL_ACCEPT))
        scope = dict(scope)
        scope["headers"] = rewritten
        await app(scope, receive, send)

    return middleware


def main() -> None:
    parser = argparse.ArgumentParser(prog="mcp-kanboard")
    parser.add_argument(
        "--http",
        action="store_true",
        help="Run with streamable-http transport (for remote clients like claude.ai). Default is stdio.",
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
        help="Skip OAuth/passphrase in --http mode. ONLY for short manual tests.",
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

    mcp_app = server.streamable_http_app()
    mcp_app = _normalize_accept_asgi(mcp_app)
    path = server.settings.streamable_http_path

    if args.insecure_no_auth:
        print(
            "[mcp-kanboard] WARNING: --insecure-no-auth set; the HTTP endpoint has NO authentication.",
            file=sys.stderr,
        )
        app = mcp_app
    else:
        passphrase = os.environ.get("MCP_PASSPHRASE", "").strip()
        if not passphrase:
            print(
                "[mcp-kanboard] MCP_PASSPHRASE env var is required in --http mode "
                "(or pass --insecure-no-auth to disable auth).",
                file=sys.stderr,
            )
            sys.exit(2)

        from mcp_kanboard.oauth import (
            OAuthState,
            build_oauth_app,
            compose_app,
            oauth_bearer_asgi,
        )

        state = OAuthState(passphrase)
        oauth_app = build_oauth_app(state)
        protected_mcp = oauth_bearer_asgi(mcp_app, state)
        app = compose_app(protected_mcp, oauth_app)
        print(
            "[mcp-kanboard] OAuth passphrase auth enabled. "
            f"Login form at /authorize. MCP at {path}.",
            file=sys.stderr,
        )

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
