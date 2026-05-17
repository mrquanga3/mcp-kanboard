from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_kanboard.client import KanboardClient


def register(mcp: FastMCP, client: KanboardClient) -> None:
    @mcp.tool()
    def kb_set_task_time(task_id: int, time_estimated: float, time_spent: float) -> bool:
        """Set the estimated and spent hours on a task."""
        return bool(
            client.call(
                "setTaskEstimateAndTimeSpent",
                {
                    "task_id": task_id,
                    "time_estimated": time_estimated,
                    "time_spent": time_spent,
                },
            )
        )

    @mcp.tool()
    def kb_get_task_time(task_id: int) -> dict[str, Any]:
        """Get estimated vs spent time for a task."""
        return client.call("getTaskTimeSpent", {"task_id": task_id})

    @mcp.tool()
    def kb_start_subtask_timer(subtask_id: int, user_id: int) -> bool:
        """Start the timer on a subtask for a given user (Kanboard's first-class timer)."""
        return bool(
            client.call("setSubtaskStartTime", {"subtask_id": subtask_id, "user_id": user_id})
        )

    @mcp.tool()
    def kb_stop_subtask_timer(subtask_id: int, user_id: int) -> bool:
        """Stop the timer on a subtask and log elapsed time."""
        return bool(
            client.call("setSubtaskEndTime", {"subtask_id": subtask_id, "user_id": user_id})
        )
