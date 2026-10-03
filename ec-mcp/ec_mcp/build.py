"""Build identification for deployment verification.

Reads the git commit of the deployed checkout at runtime so QA clients
without filesystem access can verify which revision of the MCP they are
testing (see QA-BATTERY.md: T0 / deployment verification).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from ec_mcp import __version__

_FALLBACK_COMMIT = "unknown"
_REPO_DIR = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=1)
def build_commit() -> str:
    try:
        git_dir = next((p / ".git" for p in _REPO_DIR.parents if (p / ".git").exists()), None)
        if git_dir is None:
            return _FALLBACK_COMMIT
        if (git_dir / "HEAD").exists():
            head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
        elif git_dir.is_file():
            head = Path(Path.read_text(git_dir, encoding="utf-8").strip().removeprefix("gitdir:")).joinpath("HEAD").read_text(encoding="utf-8").strip()
        else:
            return _FALLBACK_COMMIT
        if head.startswith("ref:"):
            ref_path = git_dir / head[4:].strip()
            return ref_path.read_text(encoding="utf-8").strip()[:12] or _FALLBACK_COMMIT
        return head[:12] or _FALLBACK_COMMIT
    except OSError:
        return _FALLBACK_COMMIT


def build_info() -> dict[str, str]:
    return {"package_version": __version__, "git_commit": build_commit()}
