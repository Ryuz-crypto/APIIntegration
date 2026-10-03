#!/usr/bin/env python3
"""Privileged worker for ec-mcp web updates.

The web process only writes a small validated request. This worker revalidates
all fields, performs a fast-forward update, runs tests, restarts services and
rolls back code if installation or verification fails.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
BRANCH = re.compile(r"^[A-Za-z0-9._/-]+$")
SHA = re.compile(r"^[0-9a-f]{40}$")
UNIT = re.compile(r"^[A-Za-z0-9_.@-]+\.service$")


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def run(command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None, timeout: int = 900) -> str:
    result = subprocess.run(  # noqa: S603  # nosec B603
        command,
        cwd=cwd,
        env=env,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout,
    )
    if result.returncode:
        output = result.stdout[-6000:]
        raise RuntimeError(f"{Path(command[0]).name} terminó con código {result.returncode}.\n{output}")
    return result.stdout.strip()


def write_status(state: Path, payload: dict) -> None:
    state.mkdir(mode=0o750, parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".status.", dir=state)
    try:
        directory_stat = state.stat()
        os.fchmod(descriptor, 0o640)
        try:
            os.fchown(descriptor, directory_stat.st_uid, directory_stat.st_gid)
        except PermissionError:
            pass
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, state / "status.json")
    finally:
        Path(temporary_name).unlink(missing_ok=True)


def read_request(state: Path) -> dict | None:
    state.mkdir(mode=0o750, parents=True, exist_ok=True)
    directory = os.open(state, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        try:
            descriptor = os.open("request.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        except FileNotFoundError:
            return None
        with os.fdopen(descriptor, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError("La solicitud no es un archivo regular.")
            raw = stream.read(8193)
            if len(raw) > 8192:
                raise ValueError("La solicitud es demasiado grande.")
        os.unlink("request.json", dir_fd=directory)
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("Solicitud inválida.")
        return payload
    finally:
        os.close(directory)


def git_environment(settings: dict[str, str], state: Path) -> tuple[dict[str, str], Path | None]:
    environment = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    token = settings.get("EC_UPDATE_GITHUB_TOKEN", "")
    if not token:
        return environment, None
    helper = state / ".git-askpass"
    helper.write_text(
        "#!/bin/sh\ncase \"$1\" in *Username*) printf '%s\\n' \"$EC_GIT_USER\";; *) printf '%s\\n' \"$EC_GIT_TOKEN\";; esac\n",
        encoding="utf-8",
    )
    helper.chmod(0o700)
    environment.update(
        {
            "GIT_ASKPASS": str(helper),
            "EC_GIT_USER": settings.get("EC_UPDATE_GITHUB_USER", "x-access-token") or "x-access-token",
            "EC_GIT_TOKEN": token,
        }
    )
    return environment, helper


def validate_request(request: dict, settings: dict[str, str]) -> tuple[str, str, str]:
    repository = str(request.get("repository", ""))
    branch = str(request.get("branch", ""))
    commit = str(request.get("commit", "")).lower()
    if not REPOSITORY.fullmatch(repository):
        raise ValueError("Repositorio inválido.")
    if not BRANCH.fullmatch(branch) or ".." in branch:
        raise ValueError("Rama inválida.")
    if not SHA.fullmatch(commit):
        raise ValueError("Commit inválido.")
    if repository != settings.get("EC_UPDATE_REPOSITORY", "Ryuz-crypto/APIIntegration"):
        raise ValueError("El repositorio solicitado no coincide con la configuración.")
    if branch != settings.get("EC_UPDATE_BRANCH", "main"):
        raise ValueError("La rama solicitada no coincide con la configuración.")
    return repository, branch, commit


def backup(state: Path, project: Path, previous: str) -> Path:
    destination = state / "backups" / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    destination.mkdir(mode=0o700, parents=True)
    environment = project / ".env"
    if environment.is_file():
        shutil.copy2(environment, destination / ".env")
    (destination / "metadata.json").write_text(
        json.dumps({"created_at": datetime.now(UTC).isoformat(), "previous_commit": previous}, indent=2),
        encoding="utf-8",
    )
    return destination


def unit_exists(name: str) -> bool:
    if not UNIT.fullmatch(name):
        raise ValueError(f"Nombre de servicio inválido: {name}")
    result = subprocess.run(  # noqa: S603  # nosec B603
        ["/usr/bin/systemctl", "cat", name],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=15,
    )
    return result.returncode == 0


def restart_services(settings: dict[str, str]) -> None:
    for key in ("EC_UPDATE_SERVICE_NAME", "EC_UPDATE_ADMIN_SERVICE_NAME"):
        name = settings.get(key, "")
        if name and unit_exists(name):
            run(["/usr/bin/systemctl", "restart", name], timeout=90)


def install_update(request: dict, settings: dict[str, str], state: Path) -> tuple[str, Path]:
    repository, branch, expected = validate_request(request, settings)
    project = Path(settings.get("EC_UPDATE_PROJECT_DIR") or Path.cwd()).resolve()
    if not (project / "pyproject.toml").is_file():
        raise ValueError("EC_UPDATE_PROJECT_DIR no contiene pyproject.toml.")
    root = Path(run(["/usr/bin/git", "-C", str(project), "rev-parse", "--show-toplevel"], timeout=20)).resolve()
    previous = run(["/usr/bin/git", "-C", str(root), "rev-parse", "HEAD"], timeout=20).lower()
    dirty = run(["/usr/bin/git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"], timeout=20)
    if dirty:
        raise RuntimeError("El checkout tiene cambios rastreados; se cancela para no sobrescribirlos.")
    saved = backup(state, project, previous)
    environment, helper = git_environment(settings, state)
    changed = False
    try:
        url = f"https://github.com/{repository}.git"
        run(["/usr/bin/git", "-C", str(root), "fetch", "--no-tags", url, branch], env=environment, timeout=180)
        fetched = run(["/usr/bin/git", "-C", str(root), "rev-parse", "FETCH_HEAD"], timeout=20).lower()
        if fetched != expected:
            raise RuntimeError("GitHub cambió desde la validación; la actualización fue cancelada.")
        run(["/usr/bin/git", "-C", str(root), "merge-base", "--is-ancestor", previous, fetched], timeout=20)
        run(["/usr/bin/git", "-C", str(root), "merge", "--ff-only", fetched], timeout=90)
        changed = fetched != previous
        python = project / ".venv" / "bin" / "python"
        if not python.is_file():
            raise RuntimeError("No existe .venv/bin/python; ejecuta el instalador de ec-mcp.")
        run([str(python), "-m", "pip", "install", "-e", str(project)], timeout=600)
        run([str(python), "-m", "pytest", "tests", "-q"], cwd=project, timeout=900)
        restart_services(settings)
    except Exception:
        if changed:
            run(["/usr/bin/git", "-C", str(root), "reset", "--hard", previous], timeout=90)  # nosec B607
            python = project / ".venv" / "bin" / "python"
            if python.is_file():
                run([str(python), "-m", "pip", "install", "-e", str(project)], timeout=600)
            restart_services(settings)
        raise
    finally:
        if helper:
            helper.unlink(missing_ok=True)
        environment.pop("EC_GIT_TOKEN", None)
    return expected, saved


def public_diagnostic(error: Exception, settings: dict[str, str]) -> str:
    value = str(error)
    for secret in (settings.get("EC_UPDATE_GITHUB_TOKEN", ""), settings.get("EC_ORCHESTRATOR_API_KEY", "")):
        if secret:
            value = value.replace(secret, "[REDACTED]")
    value = re.sub(r"(?i)(token|password|secret|authorization)[=: ]+\S+", r"\1=[REDACTED]", value)
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    return "\n".join(lines[-18:])[-3000:] or type(error).__name__


def main() -> None:
    project = Path(os.environ.get("EC_UPDATE_PROJECT_DIR", Path.cwd())).resolve()
    env_file = Path(os.environ.get("EC_MCP_ENV_FILE", project / ".env"))
    settings = {**load_env(env_file), **os.environ}
    state = Path(settings.get("EC_UPDATE_STATE_DIR", "/var/lib/ec-mcp-update"))
    try:
        request = read_request(state)
    except Exception as exc:
        write_status(state, {"state": "error", "message": "Solicitud inválida.", "diagnostic": public_diagnostic(exc, settings)})
        return
    if request is None:
        return
    action = str(request.get("action", ""))
    write_status(state, {"state": "running", "action": action, "message": "Operación en curso."})
    try:
        if action == "restart":
            restart_services(settings)
            result = {"state": "success", "action": action, "message": "Servicios reiniciados."}
        elif action == "update":
            commit, saved = install_update(request, settings, state)
            result = {
                "state": "success",
                "action": action,
                "commit": commit,
                "backup": str(saved),
                "message": "Actualización instalada, probada y aplicada.",
            }
        else:
            raise ValueError("Acción no permitida.")
        result["completed_at"] = datetime.now(UTC).isoformat()
        write_status(state, result)
    except Exception as exc:
        write_status(
            state,
            {
                "state": "error",
                "action": action,
                "message": "La operación falló; se conservó la instalación anterior.",
                "diagnostic": public_diagnostic(exc, settings),
            },
        )
        raise


if __name__ == "__main__":
    main()
