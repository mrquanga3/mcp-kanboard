from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_kanboard.client import KanboardClient


def register(mcp: FastMCP, client: KanboardClient) -> None:
    @mcp.tool()
    def kb_search_tasks(project_id: int, query: str) -> list[dict[str, Any]]:
        """Search tasks in a project using Kanboard's query DSL.

        Examples:
          'assignee:me status:open'
          'color:red category:Bug'
          'due:tomorrow'
        """
        return client.call("searchTasks", {"project_id": project_id, "query": query}) or []
