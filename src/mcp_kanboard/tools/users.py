from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_kanboard.client import KanboardClient
from mcp_kanboard.guards import require_confirm


def register(mcp: FastMCP, client: KanboardClient) -> None:
    @mcp.tool()
    def kb_list_users() -> list[dict[str, Any]]:
        """List all users."""
        return client.call("getAllUsers") or []

    @mcp.tool()
    def kb_get_user(user_id: int) -> dict[str, Any]:
        """Get a user by id."""
        return client.call("getUser", {"user_id": user_id})

    @mcp.tool()
    def kb_get_user_by_name(username: str) -> dict[str, Any]:
        """Get a user by their login name."""
        return client.call("getUserByName", {"username": username})

    @mcp.tool()
    def kb_me() -> dict[str, Any]:
        """Get the currently authenticated user (the owner of the API token)."""
        return client.call("getMe")

    @mcp.tool()
    def kb_create_user(
        username: str,
        password: str,
        name: str | None = None,
        email: str | None = None,
        role: str = "app-user",
    ) -> int:
        """Create a user. role: 'app-admin' | 'app-manager' | 'app-user'. Requires admin token."""
        params: dict[str, Any] = {"username": username, "password": password, "role": role}
        if name is not None:
            params["name"] = name
        if email is not None:
            params["email"] = email
        return client.call("createUser", params)

    @mcp.tool()
    def kb_update_user(
        user_id: int,
        username: str | None = None,
        name: str | None = None,
        email: str | None = None,
        role: str | None = None,
    ) -> bool:
        """Update a user's profile fields."""
        params: dict[str, Any] = {"id": user_id}
        if username is not None:
            params["username"] = username
        if name is not None:
            params["name"] = name
        if email is not None:
            params["email"] = email
        if role is not None:
            params["role"] = role
        return bool(client.call("updateUser", params))

    @mcp.tool()
    def kb_change_user_role(project_id: int, user_id: int, role: str) -> bool:
        """Change a user's role within a project. role: 'project-manager' | 'project-member' | 'project-viewer'."""
        return bool(
            client.call(
                "changeProjectUserRole",
                {"project_id": project_id, "user_id": user_id, "role": role},
            )
        )

    @mcp.tool()
    def kb_delete_user(user_id: int, confirm: bool = False) -> dict[str, Any]:
        """Permanently delete a user. Set confirm=true to proceed."""
        require_confirm(confirm, f"delete user {user_id}")
        ok = bool(client.call("removeUser", {"user_id": user_id}))
        return {"removed": ok, "user_id": user_id}
