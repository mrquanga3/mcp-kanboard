# mcp-kanboard

A [Model Context Protocol](https://modelcontextprotocol.io) server that exposes the [Kanboard](https://kanboard.org) JSON-RPC API as tools for Claude Code (or any MCP-compatible client).

## Features

- ~55 tools across Projects, Tasks, Comments, Subtasks, Users, Categories, Tags, Search, Time tracking, and File attachments
- Works with both local and remote Kanboard instances (switch via env vars)
- Supports Application tokens (admin) and Personal tokens
- Destructive operations require an explicit `confirm=true` parameter
- Sync JSON-RPC client built on `httpx` with automatic retry on transient network errors

## Prerequisites

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) (or `pip` + a venv)
- A reachable Kanboard instance and an API token from either:
  - **Application token** (recommended for admin/automation): Kanboard → Settings → API. Username is always `jsonrpc`.
  - **Personal token**: Kanboard → My Profile → Actions → API. Username is your login.

## Install

```powershell
cd d:\mcp-kanboard
uv sync
```

## Configure

Copy the template and fill in your endpoint + token:

```powershell
Copy-Item .env.example .env
notepad .env
```

| Variable | Default | Purpose |
|---|---|---|
| `KANBOARD_URL` | _required_ | Base URL or full `/jsonrpc.php` endpoint |
| `KANBOARD_API_TOKEN` | _required_ | API token (Application or Personal) |
| `KANBOARD_USERNAME` | `jsonrpc` | `jsonrpc` for App tokens; your login for Personal tokens |
| `KANBOARD_TIMEOUT` | `30` | HTTP timeout in seconds |
| `KANBOARD_MAX_ATTACHMENT_MB` | `25` | Hard cap for upload/download size |
| `KANBOARD_VERIFY_SSL` | `true` | Set to `false` for self-signed remote certs |

`.env` is only loaded when running locally (smoke test, `mcp dev`). When Claude Code launches the server, env vars come from the `mcpServers` config block.

## Smoke test

```powershell
uv run mcp-kanboard-smoke
```

Expected: prints the endpoint, Kanboard version, and the first few projects. Non-zero exit means auth or connectivity is broken — fix that before wiring Claude Code.

## Interactive testing with the MCP Inspector

```powershell
uv run mcp dev src\mcp_kanboard\server.py
```

Opens a browser UI where you can invoke any tool by hand. Useful to verify:
- `kb_list_projects` returns data
- `kb_delete_task` without `confirm` errors out
- `kb_delete_task` with `confirm=true` succeeds
- `kb_upload_task_file` + `kb_download_task_file` round-trip

## Claude Code integration

The recommended way is the `claude mcp add` command — it writes the user-scope config for you and uses `uvx` to fetch/run directly from GitHub (no clone needed):

```powershell
claude mcp add kanboard -s user `
  -e KANBOARD_URL=http://localhost/kanboard `
  -e KANBOARD_USERNAME=jsonrpc `
  -e KANBOARD_API_TOKEN=<your_token> `
  -- uvx --from git+https://github.com/mrquanga3/mcp-kanboard mcp-kanboard
```

Restart Claude Code. Verify with `claude mcp list` — should show `kanboard ✓ Connected`.

To switch between local and remote, or change the token: `claude mcp remove kanboard -s user` and re-add, or edit `%USERPROFILE%\.claude.json` under `mcpServers.kanboard.env` and restart Claude Code.

To pull the latest version after a `git push` to this repo:

```powershell
uvx --refresh --from git+https://github.com/mrquanga3/mcp-kanboard mcp-kanboard --help
```

Then restart Claude Code.

## Using it from claude.ai (web)

claude.ai's "Custom Connectors" require a remote HTTPS MCP URL and discover auth via OAuth 2.1. Kanboard usually runs on `localhost`, so the cleanest setup is to host the MCP locally with HTTP transport and expose it through an ngrok tunnel. A PowerShell helper does the wiring.

**One-time setup:**
1. Install [ngrok](https://ngrok.com/download), run `ngrok config add-authtoken <YOUR_TOKEN>` once.
2. Pick a passphrase and add it to `.env`:
   ```
   MCP_PASSPHRASE=any_string_youll_remember
   ```

**Start:**
```powershell
.\scripts\start-web.ps1
```

The script kills any prior run, starts `mcp-kanboard --http` (OAuth-protected), starts `ngrok http 8765`, reads the public URL from ngrok's local API, and prints:

```
Name:        Kanboard
Remote URL:  https://<random>.ngrok-free.app/mcp
Auth:        OAuth + passphrase
On connect:  claude.ai will pop a browser window.
             Type your MCP_PASSPHRASE there, click Authorize.
```

In claude.ai → Settings → Connectors → **Add custom connector**, paste the Name and Remote URL (leave Advanced settings empty). Click Add. claude.ai pops a browser window — type the passphrase, click Authorize, done. The connector caches the issued tokens; you won't be asked again until the server restarts or refresh tokens expire (30 days).

**Stop:** `.\scripts\stop-web.ps1`

**State**: `.web-mcp-state.json` (gitignored) caches URL and PIDs so re-running the script reliably kills the previous instance. Issued OAuth tokens live in process memory — server restart invalidates them and claude.ai silently re-pops the passphrase form.

**Manual / non-Windows**: `MCP_PASSPHRASE=xxx uv run mcp-kanboard --http --port 8765` then point any tunnel at `127.0.0.1:8765`. MCP endpoint at `/mcp`; OAuth endpoints at `/authorize`, `/token`, `/register`, and `/.well-known/oauth-*`. Use `--insecure-no-auth` for a quick test without OAuth (NOT recommended — anyone with the URL gets full Kanboard access).

**Security notes**:
- Passphrase lives only in `.env` (gitignored) and never leaves your machine. The form's POST is HTTPS via ngrok.
- Token issuance uses PKCE S256; access tokens last 1h, refresh tokens 30d.
- ngrok-free URLs rotate on every restart — claude.ai will mark the old connector offline and you'll need to update its URL.
- For multi-user or production-grade auth (Google login, etc.), put a Cloudflare Tunnel + Access policy in front instead of ngrok.

## Using it from Claude Code

Once registered, just describe what you want in natural language. Claude picks the right `kb_*` tool. Examples:

| Prompt | Tools invoked |
|---|---|
| _"liệt kê các project trên Kanboard"_ | `kb_list_projects` |
| _"show tasks in project 1 that are still open"_ | `kb_list_tasks(project_id=1, status_id=1)` |
| _"create a task 'Fix login bug' in project 1 assigned to me, due tomorrow"_ | `kb_me` + `kb_create_task` |
| _"move task #42 to the 'Done' column"_ | `kb_get_task` (find current column) → `kb_move_task_position` |
| _"add a comment 'Reviewed' to task 42"_ | `kb_me` + `kb_create_comment` |
| _"find all overdue tasks assigned to user 'alice' in project 1"_ | `kb_search_tasks(project_id=1, query="assignee:alice due:overdue")` |
| _"upload screenshot.png as an attachment on task 42"_ | `kb_upload_task_file(local_path=..., filename=...)` |
| _"delete task 42"_ | `kb_delete_task` — first call errors asking for `confirm=true`; Claude confirms with you then retries |

**Search DSL** (`kb_search_tasks`): Kanboard accepts filters like `assignee:me`, `status:open`, `color:red`, `category:Bug`, `due:tomorrow`, `tag:urgent`. Combine with spaces (AND): `assignee:me status:open due:overdue`.

**Destructive tools** (delete_*, remove_user) refuse to run without `confirm=true`. Claude will surface the error and ask you to confirm before re-calling — this is the safety net, don't disable it.

**Switching context**: if you have both local and remote Kanboards, register them as two separate MCP servers with different names (e.g. `kanboard_local` and `kanboard_remote`) and different `-e` env values. Each gets its own `kb_*` tool namespace in Claude Code.

## Tool reference

All tools are prefixed `kb_`. Bold entries are destructive and require `confirm=true`.

**Projects** — `kb_list_projects`, `kb_get_project`, `kb_get_project_by_name`, `kb_get_project_activity`, `kb_create_project`, `kb_update_project`, `kb_enable_project`, `kb_disable_project`, **`kb_delete_project`**

**Tasks** — `kb_list_tasks`, `kb_get_task`, `kb_get_task_by_reference`, `kb_get_overdue_tasks`, `kb_get_overdue_tasks_by_project`, `kb_create_task`, `kb_update_task`, `kb_open_task`, `kb_close_task`, `kb_move_task_position`, `kb_move_task_to_project`, `kb_duplicate_task_to_project`, `kb_assign_task`, **`kb_delete_task`**

**Comments** — `kb_list_comments`, `kb_get_comment`, `kb_create_comment`, `kb_update_comment`, **`kb_delete_comment`**

**Subtasks** — `kb_list_subtasks`, `kb_get_subtask`, `kb_create_subtask`, `kb_update_subtask`, **`kb_delete_subtask`**

**Users** — `kb_list_users`, `kb_get_user`, `kb_get_user_by_name`, `kb_me`, `kb_create_user`, `kb_update_user`, `kb_change_user_role`, **`kb_delete_user`**

**Categories** — `kb_list_categories`, `kb_get_category`, `kb_create_category`, `kb_update_category`, **`kb_delete_category`**

**Tags** — `kb_list_tags`, `kb_create_tag`, `kb_update_tag`, **`kb_delete_tag`**, `kb_set_task_tags`

**Search** — `kb_search_tasks` (uses Kanboard's query DSL: `assignee:me status:open`, `color:red`, `due:tomorrow`)

**Time tracking** — `kb_set_task_time`, `kb_get_task_time`, `kb_start_subtask_timer`, `kb_stop_subtask_timer`

**Files** — `kb_list_task_files`, `kb_get_task_file_info`, `kb_upload_task_file`, `kb_download_task_file`, **`kb_delete_task_file`**

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `Kanboard authentication failed` | `KANBOARD_USERNAME` should be `jsonrpc` for an Application token; your login for a Personal token |
| `Non-JSON response from Kanboard` | URL points to the wrong path. Endpoint must end in `/jsonrpc.php` |
| `SSL: CERTIFICATE_VERIFY_FAILED` | Self-signed cert on remote. Set `KANBOARD_VERIFY_SSL=false` |
| `Unknown Kanboard method: X` | Your Kanboard version doesn't expose that endpoint (Kanboard 1.2.20+ recommended) |
| Tool errors with `Refusing to delete …` | Pass `confirm=true` to the destructive tool |

## Out of scope (v1)

- Webhooks / event subscriptions
- Custom fields, automation rules
- Swimlane / Column / Group CRUD
- Task links (`createTaskLink`, etc.)
- LDAP / OAuth flows, backups, import/export
- Caching layer, async transport
- Multiple Kanboard instances in a single process (switching is restart-based)
