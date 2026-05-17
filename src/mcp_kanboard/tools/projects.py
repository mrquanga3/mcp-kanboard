from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_kanboard.client import KanboardClient
from mcp_kanboard.guards import require_confirm


def register(mcp: FastMCP, client: KanboardClient) -> None:
    @mcp.tool()
    def kb_list_projects() -> list[dict[str, Any]]:
        """List all projects visible to the API user."""
        return client.call("getAllProjects") or []

    @mcp.tool()
    def kb_get_project(project_id: int) -> dict[str, Any]:
        """Get a project by id."""
        return client.call("getProjectById", {"project_id": project_id})

    @mcp.tool()
    def kb_get_project_by_name(name: str) -> dict[str, Any]:
        """Get a project by its exact name."""
        return client.call("getProjectByName", {"name": name})

    @mcp.tool()
    def kb_get_project_activity(project_id: int) -> list[dict[str, Any]]:
        """Get recent activity events for a project."""
        return client.call("getProjectActivity", {"project_id": project_id}) or []

    @mcp.tool()
    def kb_create_project(
        name: str,
        description: str | None = None,
        identifier: str | None = None,
        owner_id: int | None = None,
    ) -> int:
        """Create a new project. Returns the new project id."""
        params: dict[str, Any] = {"name": name}
        if description is not None:
            params["description"] = description
        if identifier is not None:
            params["identifier"] = identifier
        if owner_id is not None:
            params["owner_id"] = owner_id
        return client.call("createProject", params)

    @mcp.tool()
    def kb_update_project(
        project_id: int,
        name: str | None = None,
        description: str | None = None,
        identifier: str | None = None,
        owner_id: int | None = None,
    ) -> bool:
        """Update fields on a project. Only provided fields are changed."""
        params: dict[str, Any] = {"project_id": project_id}
        if name is not None:
            params["name"] = name
        if description is not None:
            params["description"] = description
        if identifier is not None:
            params["identifier"] = identifier
        if owner_id is not None:
            params["owner_id"] = owner_id
        return bool(client.call("updateProject", params))

    @mcp.tool()
    def kb_enable_project(project_id: int) -> bool:
        """Enable (activate) a project."""
        return bool(client.call("enableProject", {"project_id": project_id}))

    @mcp.tool()
    def kb_disable_project(project_id: int) -> bool:
        """Disable (archive) a project."""
        return bool(client.call("disableProject", {"project_id": project_id}))

    @mcp.tool()
    def kb_delete_project(project_id: int, confirm: bool = False) -> dict[str, Any]:
        """Permanently delete a project. Set confirm=true to proceed."""
        require_confirm(confirm, f"delete project {project_id}")
        ok = bool(client.call("removeProject", {"project_id": project_id}))
        return {"removed": ok, "project_id": project_id}
