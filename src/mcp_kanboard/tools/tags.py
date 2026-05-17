from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_kanboard.client import KanboardClient
from mcp_kanboard.guards import require_confirm


def register(mcp: FastMCP, client: KanboardClient) -> None:
    @mcp.tool()
    def kb_list_tags(project_id: int) -> list[dict[str, Any]]:
        """List all tags scoped to a project."""
        return client.call("getTagsByProject", {"project_id": project_id}) or []

    @mcp.tool()
    def kb_create_tag(project_id: int, tag: str) -> int:
        """Create a tag in a project. Returns the new tag id."""
        return client.call("createTag", {"project_id": project_id, "tag": tag})

    @mcp.tool()
    def kb_update_tag(tag_id: int, tag: str) -> bool:
        """Rename a tag."""
        return bool(client.call("updateTag", {"tag_id": tag_id, "tag": tag}))

    @mcp.tool()
    def kb_delete_tag(tag_id: int, confirm: bool = False) -> dict[str, Any]:
        """Permanently delete a tag. Set confirm=true to proceed."""
        require_confirm(confirm, f"delete tag {tag_id}")
        ok = bool(client.call("removeTag", {"tag_id": tag_id}))
        return {"removed": ok, "tag_id": tag_id}

    @mcp.tool()
    def kb_set_task_tags(project_id: int, task_id: int, tags: list[str]) -> bool:
        """Replace the full set of tags on a task. Creates tags that don't yet exist in the project."""
        return bool(
            client.call(
                "setTaskTags",
                {"project_id": project_id, "task_id": task_id, "tags": tags},
            )
        )
