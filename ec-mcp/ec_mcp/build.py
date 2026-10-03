"""Build identity exposed by the MCP for deployment verification.

The server may run from an editable checkout, a wheel, or a container. A
deployment can therefore provide EC_MCP_BUILD_COMMIT explicitly; when it
is absent we still try to resolve the commit from the local Git checkout.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from ec_mcp import __version__

_FALLBACK_COMMIT = "unknown"
_BUILD_COMMIT_ENV = "EC_MCP_BUILD_COMMIT"
_REPO_DIR = Path(__file__).resolve().parent.parent


def _git_dir() -> Path | None:
    for parent in (_REPO_DIR, *_REPO_DIR.parents):
        candidate = parent / ".git"
        if candidate.is_dir():
            return candidate
        if candidate.is_file():
            try:
                pointer = candidate.read_text(encoding="utf-8").strip()
            except OSError:
                continue
            if pointer.startswith("gitdir:"):
                value = Path(pointer[7:].strip())
                return value if value.is_absolute() else (candidate.parent / value).resolve()
    return None


def _head_commit(git_dir: Path) -> str:
    head_file = git_dir / "HEAD"
    head = head_file.read_text(encoding="utf-8").strip()
    if head.startswith("ref:"):
        ref = head[4:].strip()
        ref_file = git_dir / ref
        if ref_file.is_file():
            return ref_file.read_text(encoding="utf-8").strip()
        packed_refs = git_dir / "packed-refs"
        if packed_refs.is_file():
            for line in packed_refs.read_text(encoding="utf-8").splitlines():
                if line and not line.startswith("#") and not line.startswith("^"):
                    commit, packed_ref = line.split(" ", 1)
                    if packed_ref == ref:
                        return commit
        return ""
    return head


@lru_cache(maxsize=1)
def build_commit() -> str:
    override = os.environ.get(_BUILD_COMMIT_ENV, "").strip()
    if override:
        return override[:40]

    try:
        git_dir = _git_dir()
        if git_dir is None:
            return _FALLBACK_COMMIT
        commit = _head_commit(git_dir).strip()
        return commit[:40] or _FALLBACK_COMMIT
    except (OSError, ValueError):
        return _FALLBACK_COMMIT


def build_info() -> dict[str, str]:
    return {
        "package_version": __version__,
        "git_commit": build_commit(),
    }
