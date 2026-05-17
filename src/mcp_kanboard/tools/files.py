from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_kanboard.client import KanboardClient
from mcp_kanboard.errors import KanboardError
from mcp_kanboard.guards import require_confirm


def _enforce_size(num_bytes: int, max_mb: int, direction: str) -> None:
    max_bytes = max_mb * 1024 * 1024
    if num_bytes > max_bytes:
        raise KanboardError(
            f"Refusing to {direction} {num_bytes / (1024 * 1024):.1f} MB "
            f"(limit: {max_mb} MB). Raise KANBOARD_MAX_ATTACHMENT_MB or handle out-of-band."
        )


def register(mcp: FastMCP, client: KanboardClient) -> None:
    @mcp.tool()
    def kb_list_task_files(task_id: int) -> list[dict[str, Any]]:
        """List all files attached to a task."""
        return client.call("getAllTaskFiles", {"task_id": task_id}) or []

    @mcp.tool()
    def kb_get_task_file_info(file_id: int) -> dict[str, Any]:
        """Get metadata for a single task file (does not include contents)."""
        return client.call("getTaskFile", {"file_id": file_id})

    @mcp.tool()
    def kb_upload_task_file(
        project_id: int,
        task_id: int,
        filename: str,
        local_path: str | None = None,
        content_base64: str | None = None,
    ) -> int:
        """Attach a file to a task. Provide EITHER local_path (read from disk) OR content_base64.

        Returns the new file id.
        """
        if (local_path is None) == (content_base64 is None):
            raise KanboardError("Provide exactly one of local_path or content_base64.")

        max_mb = client.settings.max_attachment_mb

        if local_path is not None:
            path = Path(local_path)
            if not path.is_file():
                raise KanboardError(f"File not found: {local_path}")
            data = path.read_bytes()
            _enforce_size(len(data), max_mb, "upload")
            blob = base64.b64encode(data).decode("ascii")
        else:
            try:
                decoded = base64.b64decode(content_base64, validate=True)
            except (ValueError, TypeError) as exc:
                raise KanboardError(f"content_base64 is not valid base64: {exc}") from exc
            _enforce_size(len(decoded), max_mb, "upload")
            blob = content_base64

        return client.call(
            "createTaskFile",
            {
                "project_id": project_id,
                "task_id": task_id,
                "filename": filename,
                "blob": blob,
            },
        )

    @mcp.tool()
    def kb_download_task_file(file_id: int, save_to: str | None = None) -> dict[str, Any]:
        """Download a task file. If save_to is provided, write to disk and return metadata; else return base64."""
        encoded = client.call("downloadTaskFile", {"file_id": file_id})
        if not encoded:
            raise KanboardError(f"Kanboard returned empty content for file {file_id}")
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            raise KanboardError(f"Kanboard returned non-base64 content: {exc}") from exc

        max_mb = client.settings.max_attachment_mb
        _enforce_size(len(data), max_mb, "download")

        digest = hashlib.sha256(data).hexdigest()

        if save_to is not None:
            out = Path(save_to)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
            return {"path": str(out.resolve()), "bytes": len(data), "sha256": digest}

        return {"content_base64": encoded, "bytes": len(data), "sha256": digest}

    @mcp.tool()
    def kb_delete_task_file(file_id: int, confirm: bool = False) -> dict[str, Any]:
        """Permanently delete a task file. Set confirm=true to proceed."""
        require_confirm(confirm, f"delete task file {file_id}")
        ok = bool(client.call("removeTaskFile", {"file_id": file_id}))
        return {"removed": ok, "file_id": file_id}
