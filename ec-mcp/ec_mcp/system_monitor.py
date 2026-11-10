"""Read-only host metrics for the administrative panel.

CPU utilization uses two /proc/stat samples; the first sample is unavailable.
No shell commands, environment variables or process lists are exposed.
"""

from __future__ import annotations

import os
import platform
import shutil
import threading
import time
from pathlib import Path
from typing import Any

_CPU_LOCK = threading.Lock()
_CPU_PREVIOUS: tuple[int, int] | None = None


def _cpu_sample(path: Path = Path("/proc/stat")) -> float | None:
    global _CPU_PREVIOUS
    try:
        with path.open(encoding="utf-8") as stream:
            fields = stream.readline().split()
        if fields[0] != "cpu" or len(fields) < 5:
            return None
        values = [int(value) for value in fields[1:]]
        total = sum(values[:8])
        idle = values[3] + (values[4] if len(values) > 4 else 0)
    except (OSError, ValueError, IndexError):
        return None
    with _CPU_LOCK:
        previous = _CPU_PREVIOUS
        _CPU_PREVIOUS = (total, idle)
    if not previous or total <= previous[0] or idle < previous[1]:
        return None
    return round(max(0.0, min(100.0, 100.0 * (1 - (idle - previous[1]) / (total - previous[0])))), 1)


def _memory(path: Path = Path("/proc/meminfo")) -> dict[str, int | float] | None:
    try:
        values = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition(":")
            if key in ("MemTotal", "MemAvailable"):
                values[key] = int(value.split()[0]) * 1024
        total, available = values["MemTotal"], values["MemAvailable"]
        if total <= 0:
            return None
        used = max(0, total - available)
        return {"total_bytes": total, "used_bytes": used, "used_percent": round(used * 100 / total, 1)}
    except (OSError, ValueError, KeyError, IndexError):
        return None


def host_snapshot(audit_path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "timestamp": time.time(),
        "os": {"system": platform.system(), "release": platform.release(), "architecture": platform.machine()},
        "cpu": {"cores": os.cpu_count(), "used_percent": _cpu_sample()},
        "memory": _memory(),
        "disk": None,
        "audit_log_bytes": None,
    }
    try:
        usage = shutil.disk_usage(Path.cwd())
        result["disk"] = {
            "scope": "filesystem containing admin service working directory",
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "used_percent": round(usage.used * 100 / usage.total, 1) if usage.total else None,
        }
    except OSError:
        pass
    try:
        if audit_path.is_file():
            result["audit_log_bytes"] = audit_path.stat().st_size
    except OSError:
        pass
    return result
