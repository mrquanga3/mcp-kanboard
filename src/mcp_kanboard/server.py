from __future__ import annotations

import sys

from mcp.server.fastmcp import FastMCP

from mcp_kanboard.client import KanboardClient
from mcp_kanboard.config import load_settings
from mcp_kanboard.tools import register_all


def _build() -> FastMCP:
    settings = load_settings()
    client = KanboardClient(settings)
    instance = FastMCP("kanboard")
    register_all(instance, client)
    return instance


def main() -> None:
    try:
        server = _build()
    except RuntimeError as exc:
        print(f"[mcp-kanboard] startup failed: {exc}", file=sys.stderr)
        sys.exit(2)
    server.run()


# Eager instance for `mcp dev src/mcp_kanboard/server.py`.
# Requires env vars to be present at import time.
try:
    mcp = _build()
except RuntimeError:
    mcp = None  # type: ignore[assignment]


if __name__ == "__main__":
    main()
