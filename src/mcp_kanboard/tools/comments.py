from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_kanboard.client import KanboardClient
from mcp_kanboard.guards import require_confirm


def register(mcp: FastMCP, client: KanboardClient) -> None:
    @mcp.tool()
    def kb_list_comments(task_id: int) -> list[dict[str, Any]]:
        """List all comments on a task."""
        return client.call("getAllComments", {"task_id": task_id}) or []

    @mcp.tool()
    def kb_get_comment(comment_id: int) -> dict[str, Any]:
        """Get a single comment by id."""
        return client.call("getComment", {"comment_id": comment_id})

    @mcp.tool()
    def kb_create_comment(task_id: int, user_id: int, content: str) -> int:
        """Add a comment to a task. Returns the new comment id."""
        return client.call(
            "createComment",
            {"task_id": task_id, "user_id": user_id, "content": content},
        )

    @mcp.tool()
    def kb_update_comment(comment_id: int, content: str) -> bool:
        """Update the body of a comment."""
        return bool(client.call("updateComment", {"id": comment_id, "content": content}))

    @mcp.tool()
    def kb_delete_comment(comment_id: int, confirm: bool = False) -> dict[str, Any]:
        """Permanently delete a comment. Set confirm=true to proceed."""
        require_confirm(confirm, f"delete comment {comment_id}")
        ok = bool(client.call("removeComment", {"comment_id": comment_id}))
        return {"removed": ok, "comment_id": comment_id}
