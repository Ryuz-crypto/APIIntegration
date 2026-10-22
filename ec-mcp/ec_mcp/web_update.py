"""GitHub release detection and privileged-update request queue for ec-mcp."""

from __future__ import annotations

import json
import os
import re
import subprocess  # nosec B404
import tempfile
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from .admin_config import read_env

_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_BRANCH = re.compile(r"^[A-Za-z0-9._/-]+$")
_SHA = re.compile(r"^[0-9a-f]{40}$")


def _settings() -> dict[str, str]:
    values = read_env()
    merged = {**values, **{key: value for key, value in os.environ.items() if key.startswith("EC_UPDATE_")}}
    return {
        "enabled": merged.get("EC_UPDATE_ALLOW_WEB", "true").lower(),
        "repository": merged.get("EC_UPDATE_REPOSITORY", "Ryuz-crypto/APIIntegration"),
        "branch": merged.get("EC_UPDATE_BRANCH", "main"),
        "username": merged.get("EC_UPDATE_GITHUB_USER", ""),
        "token": merged.get("EC_UPDATE_GITHUB_TOKEN", ""),
        "project_dir": merged.get("EC_UPDATE_PROJECT_DIR", str(Path.cwd())),
        "state_dir": merged.get("EC_UPDATE_STATE_DIR", "/var/lib/ec-mcp-update"),
    }


def _validate_source(repository: str, branch: str) -> None:
    if not _REPOSITORY.fullmatch(repository):
        raise ValueError("Repositorio inválido; usa owner/repository.")
    if not _BRANCH.fullmatch(branch) or ".." in branch:
        raise ValueError("Rama inválida.")


def _current_commit(project_dir: str) -> str:
    try:
        result = subprocess.run(  # noqa: S603  # nosec B603
            ["/usr/bin/git", "-C", project_dir, "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return os.environ.get("EC_MCP_BUILD_COMMIT", "")
    value = result.stdout.strip().lower()
    return value if _SHA.fullmatch(value) else ""


def _github_commit(repository: str, branch: str, token: str | None = None, opener=None) -> dict:
    _validate_source(repository, branch)
    url = f"https://api.github.com/repos/{repository}/commits/{branch}"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "ec-mcp-updater/3"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)  # nosec B310
    open_url = opener or urllib.request.urlopen
    try:
        with open_url(request, timeout=15) as response:  # nosec B310
            payload = json.loads(response.read(1024 * 1024))
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403, 404}:
            raise ValueError(
                "GitHub rechazó la consulta. Si el repositorio es privado, guarda usuario y token con acceso de lectura."
            ) from None
        raise ValueError(f"GitHub respondió HTTP {exc.code}.") from None
    except (OSError, TimeoutError, json.JSONDecodeError) as exc:
        raise ValueError(f"No se pudo consultar GitHub: {type(exc).__name__}.") from None
    sha = str(payload.get("sha", "")).lower()
    if not _SHA.fullmatch(sha):
        raise ValueError("GitHub no devolvió un commit válido.")
    commit = payload.get("commit") if isinstance(payload.get("commit"), dict) else {}
    message = str(commit.get("message", "")).splitlines()[0][:200]
    return {
        "sha": sha,
        "short_sha": sha[:12],
        "message": message,
        "url": f"https://github.com/{repository}/commit/{sha}",
    }


def status() -> dict:
    settings = _settings()
    path = Path(settings["state_dir"]) / "status.json"
    if not path.is_file():
        return {"state": "idle"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"state": "unknown", "message": "El estado del updater no se puede leer."}
    allowed = {"state", "action", "version", "commit", "message", "diagnostic", "completed_at", "backup"}
    return {key: value for key, value in payload.items() if key in allowed}


def check(opener=None) -> dict:
    settings = _settings()
    if settings["enabled"] != "true":
        raise ValueError("Las actualizaciones web están deshabilitadas.")
    remote = _github_commit(settings["repository"], settings["branch"], settings["token"], opener=opener)
    current = _current_commit(settings["project_dir"])
    return {
        "repository": settings["repository"],
        "branch": settings["branch"],
        "private_credentials_configured": bool(settings["token"]),
        "current_commit": current,
        "current_short_sha": current[:12],
        "remote": remote,
        "update_available": bool(current and current != remote["sha"]),
        "confirmation": f"ACTUALIZAR {remote['short_sha']}",
        "status": status(),
    }


def _write_request(payload: dict) -> None:
    settings = _settings()
    directory = Path(settings["state_dir"])
    directory.mkdir(mode=0o750, parents=True, exist_ok=True)
    target = directory / "request.json"
    if target.exists():
        raise ValueError("Ya existe una operación pendiente.")
    payload = {**payload, "requested_at": datetime.now(UTC).isoformat()}
    descriptor, temporary_name = tempfile.mkstemp(prefix=".request.", dir=directory)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_name, 0o640)
        try:
            os.link(temporary_name, target)
        except FileExistsError:
            raise ValueError("Ya existe una operación pendiente.") from None
    finally:
        Path(temporary_name).unlink(missing_ok=True)


def queue_update(remote_sha: str, confirmation: str, opener=None) -> dict:
    available = check(opener=opener)
    expected = available["remote"]["sha"]
    if remote_sha != expected:
        raise ValueError("El commit remoto cambió; vuelve a buscar actualizaciones.")
    if confirmation != available["confirmation"]:
        raise ValueError(f"Escribe exactamente: {available['confirmation']}")
    if available["current_commit"] == expected:
        raise ValueError("La instalación ya está en ese commit.")
    _write_request(
        {
            "action": "update",
            "repository": available["repository"],
            "branch": available["branch"],
            "commit": expected,
        }
    )
    return {"state": "pending", "commit": expected, "message": "Actualización validada y programada."}


def check_pending_request() -> bool:
    settings = _settings()
    target = Path(settings["state_dir"]) / "request.json"
    return target.is_file()


def queue_restart() -> dict:
    if _settings()["enabled"] != "true":
        raise ValueError("El worker web está deshabilitado.")
    _write_request({"action": "restart"})
    return {"state": "pending", "action": "restart", "message": "Reinicio programado; el panel aplicará la configuración."}
