"""Bounded integrity snapshot of the current audit file, without signing claims."""
from __future__ import annotations

import hashlib
import os
import stat
from datetime import UTC, datetime
from pathlib import Path

MAX_SNAPSHOT_BYTES = 64 * 1024 * 1024


def audit_snapshot(path: Path) -> dict:
    """Hash one stable regular file. This is not a signature or an external anchor."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("El registro no es un archivo regular")
        if before.st_size > MAX_SNAPSHOT_BYTES:
            raise ValueError("El registro supera el límite de 64 MiB para esta captura")
        digest = hashlib.sha256()
        total = 0
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            while chunk := stream.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_SNAPSHOT_BYTES:
                    raise ValueError("El registro superó el límite durante la captura")
                digest.update(chunk)
        after = os.fstat(descriptor)
        current = path.stat(follow_symlinks=False)
        if (
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            or (after.st_dev, after.st_ino) != (current.st_dev, current.st_ino)
            or not stat.S_ISREG(current.st_mode)
        ):
            raise ValueError("El registro cambió durante la captura; inténtalo de nuevo")
        return {
            "schema": "ec-mcp.audit-snapshot.v1",
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "algorithm": "sha256",
            "sha256": digest.hexdigest(),
            "bytes": total,
            "scope": "active_audit_file_only",
            "signed": False,
            "externally_anchored": False,
            "trusted_timestamp": False,
            "non_repudiation_established": False,
        }
    finally:
        os.close(descriptor)
