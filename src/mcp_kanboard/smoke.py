from __future__ import annotations

import sys

from mcp_kanboard.client import KanboardClient
from mcp_kanboard.config import load_settings
from mcp_kanboard.errors import KanboardError


def main() -> int:
    try:
        settings = load_settings()
    except RuntimeError as exc:
        print(f"[config] {exc}", file=sys.stderr)
        return 2

    print(f"[smoke] endpoint: {settings.url}")
    print(f"[smoke] username: {settings.username}")

    try:
        with KanboardClient(settings) as client:
            version = client.call("getVersion")
            print(f"[smoke] kanboard version: {version}")

            projects = client.call("getAllProjects") or []
            print(f"[smoke] projects found: {len(projects)}")
            for p in projects[:5]:
                print(f"  - #{p.get('id')} {p.get('name')}")
    except KanboardError as exc:
        print(f"[smoke] FAILED: {exc}", file=sys.stderr)
        return 1

    print("[smoke] OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
