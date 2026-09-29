from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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
    ) -> dict[str, Any]:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool": tool,
            "action": action,
            "target": target,
            "result": result,
            "dry_run": dry_run,
            "details": details or {},
        }
        with self._path.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(entry) + "\n")
        return entry
