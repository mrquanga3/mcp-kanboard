from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_kanboard.client import KanboardClient
from mcp_kanboard.guards import require_confirm


def register(mcp: FastMCP, client: KanboardClient) -> None:
    @mcp.tool()
    def kb_list_tasks(project_id: int, status_id: int = 1) -> list[dict[str, Any]]:
        """List tasks in a project. status_id: 1=active (default), 0=closed."""
        return client.call("getAllTasks", {"project_id": project_id, "status_id": status_id}) or []

    @mcp.tool()
    def kb_get_task(task_id: int) -> dict[str, Any]:
        """Get a task by id."""
        return client.call("getTask", {"task_id": task_id})

    @mcp.tool()
    def kb_get_task_by_reference(project_id: int, reference: str) -> dict[str, Any]:
        """Get a task by its external reference within a project."""
        return client.call("getTaskByReference", {"project_id": project_id, "reference": reference})

    @mcp.tool()
    def kb_get_overdue_tasks() -> list[dict[str, Any]]:
        """List all overdue tasks across all projects."""
        return client.call("getOverdueTasks") or []

    @mcp.tool()
    def kb_get_overdue_tasks_by_project(project_id: int) -> list[dict[str, Any]]:
        """List overdue tasks for a single project."""
        return client.call("getOverdueTasksByProject", {"project_id": project_id}) or []

    @mcp.tool()
    def kb_create_task(
        title: str,
        project_id: int,
        column_id: int | None = None,
        owner_id: int | None = None,
        description: str | None = None,
        date_due: str | None = None,
        color_id: str | None = None,
        category_id: int | None = None,
        swimlane_id: int | None = None,
        priority: int | None = None,
        tags: list[str] | None = None,
    ) -> int:
        """Create a task. Returns the new task id. date_due format: 'YYYY-MM-DD' or unix timestamp string."""
        params: dict[str, Any] = {"title": title, "project_id": project_id}
        if column_id is not None:
            params["column_id"] = column_id
        if owner_id is not None:
            params["owner_id"] = owner_id
        if description is not None:
            params["description"] = description
        if date_due is not None:
            params["date_due"] = date_due
        if color_id is not None:
            params["color_id"] = color_id
        if category_id is not None:
            params["category_id"] = category_id
        if swimlane_id is not None:
            params["swimlane_id"] = swimlane_id
        if priority is not None:
            params["priority"] = priority
        if tags is not None:
            params["tags"] = tags
        return client.call("createTask", params)

    @mcp.tool()
    def kb_update_task(
        task_id: int,
        title: str | None = None,
        owner_id: int | None = None,
        description: str | None = None,
        date_due: str | None = None,
        color_id: str | None = None,
        category_id: int | None = None,
        priority: int | None = None,
    ) -> bool:
        """Update fields on a task. Only provided fields are changed."""
        params: dict[str, Any] = {"id": task_id}
        if title is not None:
            params["title"] = title
        if owner_id is not None:
            params["owner_id"] = owner_id
        if description is not None:
            params["description"] = description
        if date_due is not None:
            params["date_due"] = date_due
        if color_id is not None:
            params["color_id"] = color_id
        if category_id is not None:
            params["category_id"] = category_id
        if priority is not None:
            params["priority"] = priority
        return bool(client.call("updateTask", params))

    @mcp.tool()
    def kb_open_task(task_id: int) -> bool:
        """Re-open a closed task."""
        return bool(client.call("openTask", {"task_id": task_id}))

    @mcp.tool()
    def kb_close_task(task_id: int) -> bool:
        """Close (complete) a task."""
        return bool(client.call("closeTask", {"task_id": task_id}))

    @mcp.tool()
    def kb_move_task_position(
        project_id: int,
        task_id: int,
        column_id: int,
        position: int,
        swimlane_id: int = 0,
    ) -> bool:
        """Move a task to a specific column/position within a project."""
        return bool(
            client.call(
                "moveTaskPosition",
                {
                    "project_id": project_id,
                    "task_id": task_id,
                    "column_id": column_id,
                    "position": position,
                    "swimlane_id": swimlane_id,
                },
            )
        )

    @mcp.tool()
    def kb_move_task_to_project(
        task_id: int,
        project_id: int,
        swimlane_id: int | None = None,
        column_id: int | None = None,
        category_id: int | None = None,
        owner_id: int | None = None,
    ) -> bool:
        """Move a task to a different project."""
        params: dict[str, Any] = {"task_id": task_id, "project_id": project_id}
        if swimlane_id is not None:
            params["swimlane_id"] = swimlane_id
        if column_id is not None:
            params["column_id"] = column_id
        if category_id is not None:
            params["category_id"] = category_id
        if owner_id is not None:
            params["owner_id"] = owner_id
        return bool(client.call("moveTaskToProject", params))

    @mcp.tool()
    def kb_duplicate_task_to_project(task_id: int, project_id: int) -> int:
        """Duplicate a task into another project. Returns the new task id."""
        return client.call("duplicateTaskToProject", {"task_id": task_id, "project_id": project_id})

    @mcp.tool()
    def kb_assign_task(task_id: int, owner_id: int) -> bool:
        """Convenience: set the owner (assignee) of a task."""
        return bool(client.call("updateTask", {"id": task_id, "owner_id": owner_id}))

    @mcp.tool()
    def kb_delete_task(task_id: int, confirm: bool = False) -> dict[str, Any]:
        """Permanently delete a task. Set confirm=true to proceed."""
        require_confirm(confirm, f"delete task {task_id}")
        ok = bool(client.call("removeTask", {"task_id": task_id}))
        return {"removed": ok, "task_id": task_id}
