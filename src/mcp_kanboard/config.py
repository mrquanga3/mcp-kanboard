from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    url: str
    username: str
    api_token: str
    timeout_seconds: float
    max_attachment_mb: int
    verify_ssl: bool


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_url(raw: str) -> str:
    url = raw.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        raise RuntimeError(f"KANBOARD_URL must start with http:// or https:// (got: {raw!r})")
    if not url.endswith("/jsonrpc.php"):
        url = f"{url}/jsonrpc.php"
    return url


def load_settings() -> Settings:
    env_path = Path(".env")
    if env_path.exists():
        load_dotenv(env_path, override=False)

    url = os.environ.get("KANBOARD_URL", "").strip()
    token = os.environ.get("KANBOARD_API_TOKEN", "").strip()
    missing = [name for name, value in (("KANBOARD_URL", url), ("KANBOARD_API_TOKEN", token)) if not value]
    if missing:
        raise RuntimeError(
            "Missing required environment variable(s): "
            + ", ".join(missing)
            + ". Set them in the MCP server config or a local .env file."
        )

    return Settings(
        url=_normalize_url(url),
        username=os.environ.get("KANBOARD_USERNAME", "jsonrpc").strip() or "jsonrpc",
        api_token=token,
        timeout_seconds=float(os.environ.get("KANBOARD_TIMEOUT", "30")),
        max_attachment_mb=int(os.environ.get("KANBOARD_MAX_ATTACHMENT_MB", "25")),
        verify_ssl=_parse_bool(os.environ.get("KANBOARD_VERIFY_SSL"), True),
    )
