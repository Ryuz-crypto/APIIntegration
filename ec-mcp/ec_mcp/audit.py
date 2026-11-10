from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .security import redact_secrets, redact_sensitive_values


def _redact_details(details: Any) -> Any:
    """Recursively redact secrets from audit details before persisting."""
    sanitized = redact_sensitive_values(details)
    if isinstance(sanitized, dict):
        return {
            redact_secrets(str(key), []): _redact_details(value)
            for key, value in sanitized.items()
        }
    if isinstance(sanitized, list):
        return [_redact_details(item) for item in sanitized]
    if isinstance(sanitized, str):
        return redact_secrets(sanitized, [])
    return sanitized


class AuditLog:
    def __init__(self, path: Path):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        tool: str,
        action: str,
        target: str,
        result: str,
        dry_run: bool = False,
        details: dict[str, Any] | None = None,
        user: str | None = None,
    ) -> dict[str, Any]:
        entry = {
            "event_id": str(uuid.uuid4()),
            "schema": "ec-mcp.audit.v1",
            "timestamp": datetime.now(UTC).isoformat(),
            "tool": tool,
            "action": redact_secrets(str(action), []),
            "target": redact_secrets(str(target), []),
            "result": redact_secrets(str(result), []),
            "dry_run": dry_run,
            "details": _redact_details(details or {}),
        }
        if user:
            entry["user"] = redact_secrets(str(user), [])
        with self._path.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(entry) + "\n")
        return entry
