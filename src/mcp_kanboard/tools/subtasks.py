from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_kanboard.client import KanboardClient
from mcp_kanboard.guards import require_confirm


def register(mcp: FastMCP, client: KanboardClient) -> None:
    @mcp.tool()
    def kb_list_subtasks(task_id: int) -> list[dict[str, Any]]:
        """List subtasks for a task."""
        return client.call("getAllSubtasks", {"task_id": task_id}) or []

    @mcp.tool()
    def kb_get_subtask(subtask_id: int) -> dict[str, Any]:
        """Get a subtask by id."""
        return client.call("getSubtask", {"subtask_id": subtask_id})

    @mcp.tool()
    def kb_create_subtask(
        task_id: int,
        title: str,
        user_id: int | None = None,
        time_estimated: float | None = None,
        time_spent: float | None = None,
        status: int | None = None,
    ) -> int:
        """Create a subtask. status: 0=todo, 1=in_progress, 2=done."""
        params: dict[str, Any] = {"task_id": task_id, "title": title}
        if user_id is not None:
            params["user_id"] = user_id
        if time_estimated is not None:
            params["time_estimated"] = time_estimated
        if time_spent is not None:
            params["time_spent"] = time_spent
        if status is not None:
            params["status"] = status
        return client.call("createSubtask", params)

    @mcp.tool()
    def kb_update_subtask(
        subtask_id: int,
        task_id: int,
        title: str | None = None,
        user_id: int | None = None,
        time_estimated: float | None = None,
        time_spent: float | None = None,
        status: int | None = None,
    ) -> bool:
        """Update a subtask. task_id is required by Kanboard."""
        params: dict[str, Any] = {"id": subtask_id, "task_id": task_id}
        if title is not None:
            params["title"] = title
        if user_id is not None:
            params["user_id"] = user_id
        if time_estimated is not None:
            params["time_estimated"] = time_estimated
        if time_spent is not None:
            params["time_spent"] = time_spent
        if status is not None:
            params["status"] = status
        return bool(client.call("updateSubtask", params))

    @mcp.tool()
    def kb_delete_subtask(subtask_id: int, confirm: bool = False) -> dict[str, Any]:
        """Permanently delete a subtask. Set confirm=true to proceed."""
        require_confirm(confirm, f"delete subtask {subtask_id}")
        ok = bool(client.call("removeSubtask", {"subtask_id": subtask_id}))
        return {"removed": ok, "subtask_id": subtask_id}
