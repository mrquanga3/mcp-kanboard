from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_kanboard.client import KanboardClient
from mcp_kanboard.tools import (
    categories,
    comments,
    files,
    groups,
    projects,
    search,
    subtasks,
    tags,
    tasks,
    time_tracking,
    users,
)

_MODULES = (
    projects,
    tasks,
    comments,
    subtasks,
    users,
    categories,
    tags,
    search,
    time_tracking,
    files,
    groups,
)


def register_all(mcp: FastMCP, client: KanboardClient) -> None:
    for module in _MODULES:
        module.register(mcp, client)
