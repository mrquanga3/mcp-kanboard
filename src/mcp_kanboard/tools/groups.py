from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_kanboard.client import KanboardClient
from mcp_kanboard.guards import require_confirm


def register(mcp: FastMCP, client: KanboardClient) -> None:
    @mcp.tool()
    def kb_create_group(name: str, external_id: str | None = None) -> int:
        """Create a new group. Returns the new group id."""
        params: dict[str, Any] = {"name": name}
        if external_id is not None:
            params["external_id"] = external_id
        return client.call("createGroup", params)

    @mcp.tool()
    def kb_get_group(group_id: int) -> dict[str, Any]:
        """Get a group by id."""
        return client.call("getGroup", {"group_id": group_id})

    @mcp.tool()
    def kb_list_groups() -> list[dict[str, Any]]:
        """List all groups."""
        return client.call("getAllGroups") or []

    @mcp.tool()
    def kb_update_group(
        group_id: int,
        name: str,
        external_id: str | None = None,
    ) -> bool:
        """Update a group's name and/or external id. Returns true on success."""
        params: dict[str, Any] = {"group_id": group_id, "name": name}
        if external_id is not None:
            params["external_id"] = external_id
        return bool(client.call("updateGroup", params))

    @mcp.tool()
    def kb_delete_group(group_id: int, confirm: bool = False) -> dict[str, Any]:
        """Permanently delete a group. Set confirm=true to proceed."""
        require_confirm(confirm, f"delete group {group_id}")
        ok = bool(client.call("removeGroup", {"group_id": group_id}))
        return {"removed": ok, "group_id": group_id}

    @mcp.tool()
    def kb_add_group_member(group_id: int, user_id: int) -> bool:
        """Add a user to a group. Returns true on success."""
        return bool(
            client.call(
                "addGroupMember",
                {"group_id": group_id, "user_id": user_id},
            )
        )

    @mcp.tool()
    def kb_remove_group_member(group_id: int, user_id: int) -> bool:
        """Remove a user from a group. Returns true on success."""
        return bool(
            client.call(
                "removeGroupMember",
                {"group_id": group_id, "user_id": user_id},
            )
        )

    @mcp.tool()
    def kb_get_group_members(group_id: int) -> list[dict[str, Any]]:
        """Get all members (users) belonging to a group."""
        return client.call("getGroupMembers", {"group_id": group_id}) or []

    @mcp.tool()
    def kb_get_user_groups(user_id: int) -> list[dict[str, Any]]:
        """Get all groups to which a specific user belongs."""
        return client.call("getMemberGroups", {"user_id": user_id}) or []

    @mcp.tool()
    def kb_is_group_member(group_id: int, user_id: int) -> bool:
        """Check if a user is a member of a group. Returns true if yes, false otherwise."""
        return bool(
            client.call(
                "isGroupMember",
                {"group_id": group_id, "user_id": user_id},
            )
        )

    @mcp.tool()
    def kb_add_project_group(
        project_id: int,
        group_id: int,
        role: str | None = None,
    ) -> bool:
        """Grant a group access to a project. role: 'project-manager' | 'project-member' | 'project-viewer'."""
        params: dict[str, Any] = {"project_id": project_id, "group_id": group_id}
        if role is not None:
            params["role"] = role
        return bool(client.call("addProjectGroup", params))

    @mcp.tool()
    def kb_remove_project_group(project_id: int, group_id: int) -> bool:
        """Revoke a group's access to a project."""
        return bool(
            client.call(
                "removeProjectGroup",
                {"project_id": project_id, "group_id": group_id},
            )
        )

    @mcp.tool()
    def kb_change_project_group_role(
        project_id: int,
        group_id: int,
        role: str,
    ) -> bool:
        """Change the role of a group for a project. role: 'project-manager' | 'project-member' | 'project-viewer'."""
        return bool(
            client.call(
                "changeProjectGroupRole",
                {"project_id": project_id, "group_id": group_id, "role": role},
            )
        )
