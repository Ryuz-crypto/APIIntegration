#!/usr/bin/env python3
"""Privileged worker for ec-mcp web updates.

The web process only writes a small validated request. This worker revalidates
all fields, performs a fast-forward update, runs tests, restarts services and
rolls back code if installation or verification fails.
"""

from __future__ import annotations

import json
import os
import pwd
import re
import shutil
import stat
import subprocess  # nosec B404
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


def run_user(command: list[str], owner: str, *, cwd: Path | None = None, env: dict[str, str] | None = None, timeout: int = 900) -> str:
    return run(
        ["/usr/sbin/runuser", "-u", owner, "--preserve-environment", "--", *command],
        cwd=cwd,
        env=env,
        timeout=timeout,
    )


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


def git_environment(settings: dict[str, str], state: Path, uid: int, gid: int) -> tuple[dict[str, str], Path | None]:
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
    os.chown(helper, uid, gid)
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


def install_package(project: Path, python: Path, owner: str) -> None:
    command = [str(python), "-m", "pip", "install"]
    lock = project / "requirements-stable.txt"
    if lock.is_file():
        command.extend(["-r", str(lock)])
    command.extend(["-e", str(project)])
    run_user(command, owner, timeout=600)


def _ensure_writable_git_dir(root: Path, owner: str) -> None:
    """Make the git metadata writable by the project owner.

    Root-owned checkouts (clone/push done as root, or filesystems mounted
    read-only for the service user) make `git fetch` fail with
    "cannot open '.git/FETCH_HEAD': Read-only file system". Fix ownership of
    the metadata tree so the unprivileged owner can update it. Best-effort:
    if we lack permission to chown, raise a clear, actionable error.
    """
    git_dir = root / ".git"
    if not git_dir.exists():
        return
    if os.access(git_dir, os.W_OK):
        return
    if os.geteuid() != 0:
        raise RuntimeError(
            f"El directorio git {git_dir} no es escribible por el usuario del "
            "proyecto y el worker no corre como root; no se puede corregir. "
            f"Ejecuta como root: chown -R {owner}: {root}"
        )
    result = subprocess.run(  # noqa: S603  # nosec B603
        ["/usr/bin/chown", "-R", f"{owner}:", str(git_dir)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=120,
    )
    if result.returncode:
        raise RuntimeError(
            f"No se pudo corregir el propietario de {git_dir}: {result.stdout.strip()[-300:]}"
        )
    if not os.access(git_dir, os.W_OK):
        raise RuntimeError(
            f"{git_dir} sigue sin ser escribible tras corregir el propietario. "
            "Causa probable: el servicio ec-mcp-update tiene ProtectHome=read-only "
            f"y el proyecto vive bajo /home (p.ej. {root}). Quita ProtectHome=read-only "
            "de /etc/systemd/system/ec-mcp-update.service (reinstala con "
            "scripts/install_admin_service.sh) o mueve el proyecto fuera de /home."
        )


def install_update(request: dict, settings: dict[str, str], state: Path) -> tuple[str, Path]:
    repository, branch, expected = validate_request(request, settings)
    project = Path(settings.get("EC_UPDATE_PROJECT_DIR") or Path.cwd()).resolve()
    if not (project / "pyproject.toml").is_file():
        raise ValueError("EC_UPDATE_PROJECT_DIR no contiene pyproject.toml.")
    project_stat = project.stat()
    owner = pwd.getpwuid(project_stat.st_uid).pw_name
    root = Path(run_user(["/usr/bin/git", "-C", str(project), "rev-parse", "--show-toplevel"], owner, timeout=20)).resolve()
    _ensure_writable_git_dir(root, owner)
    previous = run_user(["/usr/bin/git", "-C", str(root), "rev-parse", "HEAD"], owner, timeout=20).lower()
    dirty = run_user(["/usr/bin/git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"], owner, timeout=20)
    if dirty:
        raise RuntimeError("El checkout tiene cambios rastreados; se cancela para no sobrescribirlos.")
    saved = backup(state, project, previous)
    environment, helper = git_environment(settings, state, project_stat.st_uid, project_stat.st_gid)
    changed = False
    try:
        url = f"https://github.com/{repository}.git"
        run_user(["/usr/bin/git", "-C", str(root), "fetch", "--no-tags", url, branch], owner, env=environment, timeout=180)
        fetched = run_user(["/usr/bin/git", "-C", str(root), "rev-parse", "FETCH_HEAD"], owner, timeout=20).lower()
        if fetched != expected:
            raise RuntimeError("GitHub cambió desde la validación; la actualización fue cancelada.")
        run_user(["/usr/bin/git", "-C", str(root), "merge-base", "--is-ancestor", previous, fetched], owner, timeout=20)
        run_user(["/usr/bin/git", "-C", str(root), "merge", "--ff-only", fetched], owner, timeout=90)
        changed = fetched != previous
        python = project / ".venv" / "bin" / "python"
        if not python.is_file():
            raise RuntimeError("No existe .venv/bin/python; ejecuta el instalador de ec-mcp.")
        install_package(project, python, owner)
        run_user([str(python), "-m", "pytest", "tests", "-q"], owner, cwd=project, timeout=900)
        restart_services(settings)
    except Exception:
        if changed:
            run_user(["/usr/bin/git", "-C", str(root), "reset", "--hard", previous], owner, timeout=90)  # nosec B607
            python = project / ".venv" / "bin" / "python"
            if python.is_file():
                install_package(project, python, owner)
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
    initial_project = Path.cwd().resolve()
    env_file = Path(os.environ.get("EC_MCP_ENV_FILE", initial_project / ".env"))
    settings = {**load_env(env_file), **os.environ}
    project = Path(settings.get("EC_UPDATE_PROJECT_DIR") or initial_project).resolve()
    settings["EC_UPDATE_PROJECT_DIR"] = str(project)
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
