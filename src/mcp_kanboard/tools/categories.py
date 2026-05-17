from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_kanboard.client import KanboardClient
from mcp_kanboard.guards import require_confirm


def register(mcp: FastMCP, client: KanboardClient) -> None:
    @mcp.tool()
    def kb_list_categories(project_id: int) -> list[dict[str, Any]]:
        """List all categories in a project."""
        return client.call("getAllCategories", {"project_id": project_id}) or []

    @mcp.tool()
    def kb_get_category(category_id: int) -> dict[str, Any]:
        """Get a category by id."""
        return client.call("getCategory", {"category_id": category_id})

    @mcp.tool()
    def kb_create_category(project_id: int, name: str) -> int:
        """Create a category in a project. Returns the new category id."""
        return client.call("createCategory", {"project_id": project_id, "name": name})

    @mcp.tool()
    def kb_update_category(category_id: int, name: str) -> bool:
        """Rename a category."""
        return bool(client.call("updateCategory", {"id": category_id, "name": name}))

    @mcp.tool()
    def kb_delete_category(category_id: int, confirm: bool = False) -> dict[str, Any]:
        """Permanently delete a category. Set confirm=true to proceed."""
        require_confirm(confirm, f"delete category {category_id}")
        ok = bool(client.call("removeCategory", {"category_id": category_id}))
        return {"removed": ok, "category_id": category_id}
