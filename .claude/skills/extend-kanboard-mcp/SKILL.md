---
name: extend-kanboard-mcp
description: Add a new Kanboard JSON-RPC method as a tool to the mcp-kanboard server. Use when the user wants to expose an unsupported Kanboard endpoint (e.g. "add a tool for createTaskLink", "wrap getProjectStats", "expose swimlane CRUD"), refactor an existing tool, or change the destructive-confirm / error-mapping pattern. Triggers on requests inside the d:\mcp-kanboard repo that mention Kanboard methods not yet wrapped, or that ask to "add a tool", "expose method X", or "support endpoint Y".
---

# Extending mcp-kanboard

Add a new Kanboard JSON-RPC method as an MCP tool. This skill encodes the conventions so the new tool stays consistent with the existing ~55.

## Before you start

1. Confirm the method exists in Kanboard's API: https://docs.kanboard.org/v1/api/ — note the exact method name (camelCase), required params, and what it returns on success/failure.
2. Decide if it's **destructive** (deletes data, removes a user, drops a tag globally, etc.). Destructive tools need the `confirm` guard.
3. Pick the domain module under `src/mcp_kanboard/tools/`:
   - Existing domains: `projects`, `tasks`, `comments`, `subtasks`, `users`, `categories`, `tags`, `search`, `time_tracking`, `files`.
   - For a new domain, create `tools/<domain>.py` and add it to the `_MODULES` tuple in `tools/__init__.py`.

## The pattern

Every tool is a function decorated with `@mcp.tool()` inside the module's `register(mcp, client)`. Three flavors:

### A. Read tool (GET-style)

```python
@mcp.tool()
def kb_list_<noun>(<required>: <type>) -> list[dict[str, Any]]:
    """One-line description the model will read."""
    return client.call("<kanboardMethod>", {"<param>": <value>}) or []
```

`or []` guards Kanboard's habit of returning `false`/`null` for empty result sets.

### B. Mutating tool (create/update)

Required params positional. Optional params keyword args defaulting to `None`. Only forward non-None values — Kanboard rejects many endpoints with stray nulls.

```python
@mcp.tool()
def kb_update_<noun>(
    <id>: int,
    field_a: str | None = None,
    field_b: int | None = None,
) -> bool:
    """Update fields on <noun>. Only provided fields are changed."""
    params: dict[str, Any] = {"id": <id>}
    if field_a is not None:
        params["field_a"] = field_a
    if field_b is not None:
        params["field_b"] = field_b
    return bool(client.call("<kanboardMethod>", params))
```

### C. Destructive tool

`confirm: bool = False` MUST be the last parameter. Call `require_confirm` before any RPC. Return the standard `{"removed": bool, "<id_field>": id}` shape.

```python
from mcp_kanboard.guards import require_confirm

@mcp.tool()
def kb_delete_<noun>(<id>: int, confirm: bool = False) -> dict[str, Any]:
    """Permanently delete <noun>. Set confirm=true to proceed."""
    require_confirm(confirm, f"delete <noun> {<id>}")
    ok = bool(client.call("<kanboardMethod>", {"<id_param>": <id>}))
    return {"removed": ok, "<id_field>": <id>}
```

## Conventions to follow

- **Naming**: `kb_<verb>_<noun>` snake_case. `kb_` prefix is mandatory.
- **Docstrings**: one line, present-tense, model-readable. The docstring IS the tool description shown to the LLM — keep it actionable. If the tool has a subtle gotcha (e.g. timer is subtask-level not task-level), say so explicitly.
- **Types**: use Python 3.11+ `|` unions, `list[...]`, `dict[str, Any]`. Avoid `Optional[X]` and `Dict`.
- **Return shapes**: match what Kanboard returns. For creates, return the new id (int). For updates/enables/disables, return `bool`. For deletes, return the standard removed-dict.
- **No retries on mutations**: don't add custom retry around mutating calls — `KanboardClient.call` only retries network errors, not 4xx/5xx, to avoid duplicate creates.
- **No caching**: read-through every time.
- **No comments**: code should be self-explanatory. Only annotate a non-obvious WHY (e.g. why an endpoint needs `task_id` AND `id`).

## Adding a new domain module

If the new tool doesn't fit any existing module:

1. Create `src/mcp_kanboard/tools/<domain>.py` with:
   ```python
   from __future__ import annotations
   from typing import Any
   from mcp.server.fastmcp import FastMCP
   from mcp_kanboard.client import KanboardClient
   # from mcp_kanboard.guards import require_confirm  # if destructive

   def register(mcp: FastMCP, client: KanboardClient) -> None:
       @mcp.tool()
       def kb_<verb>_<noun>(...) -> ...:
           ...
   ```
2. Add the module to `_MODULES` in `tools/__init__.py` (alphabetical or grouped by domain — pick what reads cleanly).

## Error handling (only override when you must)

`KanboardClient.call` already maps:
- HTTP 401/403 → `AuthError`
- HTTP 5xx → `KanboardError` with body snippet
- JSON-RPC `-32601` → `KanboardError("Unknown method: ...")`
- `result: false` on `get*ById` → `NotFoundError`
- `result: false` on mutating method → `KanboardError("Kanboard refused operation ...")`

Don't catch these inside tools unless you have a domain-specific message worth adding. If you do:

```python
from mcp_kanboard.errors import KanboardError, NotFoundError
try:
    result = client.call("methodName", params)
except NotFoundError:
    raise KanboardError("<domain-specific message with context>")
```

## Verify before pushing

1. **Local smoke check** — does the import still work?
   ```powershell
   uv run python -c "from mcp_kanboard.server import _build; _build()"
   ```
   Requires env vars set (or a `.env`). Catches syntax / registration errors.

2. **MCP Inspector** — interactive test:
   ```powershell
   uv run mcp dev src\mcp_kanboard\server.py
   ```
   Hit your new tool. For destructive ones: invoke without `confirm` (must error), then with `confirm=true` (must succeed).

3. **Live in Claude Code** — push, refresh `uvx` cache, restart:
   ```powershell
   git push
   uvx --refresh --from git+https://github.com/mrquanga3/mcp-kanboard mcp-kanboard --help
   ```
   Then restart Claude Code and try the tool from a prompt.

## Updating the README

If the new tool is user-facing (most are), add its name to the relevant table row in `README.md` → "Tool reference" section. Bold if destructive.

## Commit message style

`<verb> <what>: <one-line why>`. Examples:
- `Add kb_create_task_link tool wrapping createTaskLink`
- `Expose swimlane CRUD via tools/swimlanes.py`
- `Fix kb_assign_task: forward None for unassigning instead of omitting`

Include `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>` in commits made by Claude.
