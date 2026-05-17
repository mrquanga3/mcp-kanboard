from __future__ import annotations

from mcp_kanboard.errors import ConfirmRequiredError


def require_confirm(confirm: bool, action: str) -> None:
    if not confirm:
        raise ConfirmRequiredError(
            f"Refusing to {action}: this operation is destructive. "
            "Re-call with confirm=true to proceed."
        )
