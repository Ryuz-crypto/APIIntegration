#!/opt/dashboardapi-ec/venv/bin/python
"""Root-only updater. The API can queue only an exact official stable release tag."""

import http.client
import json
import os
import pwd
import re
import shutil
import stat
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

STATE = Path("/var/lib/dashboardapi-ec-update")
BACKUPS = Path("/var/backups/dashboardapi-ec")
REPOSITORY = "https://github.com/Ryuz-crypto/APIIntegration.git"
PACKAGE_CACHE = STATE / "packages"
TAG_PATTERN = re.compile(r"^v\d+\.\d+\.\d+-stable$")


def _account():
    return pwd.getpwnam("dashboardapi")


def write_status(payload: dict) -> None:
    STATE.mkdir(mode=0o750, parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=STATE)
    try:
        account = _account()
        os.fchmod(fd, 0o640)
        os.fchown(fd, account.pw_uid, account.pw_gid)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream)
        os.replace(name, STATE / "status.json")
    finally:
        Path(name).unlink(missing_ok=True)


def run(command: list[str], *, cwd: Path | None = None, timeout: int = 900) -> None:
    result = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
    )
    if result.returncode:
        output = result.stdout.decode(errors="replace")[-6000:]
        raise RuntimeError(
            f"Command {Path(command[0]).name} failed with exit code "
            f"{result.returncode}.\n{output}"
        )


def installed_package() -> Path | None:
    try:
        version = subprocess.run(
            ["/usr/bin/dpkg-query", "-W", "-f=${Version}", "dashboardapi-ec"],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    matches = list(PACKAGE_CACHE.glob(f"dashboardapi-ec_{version}_*.deb"))
    return matches[0] if len(matches) == 1 else None


def verify_tag(version: str) -> None:
    if not TAG_PATTERN.fullmatch(version):
        raise ValueError("Invalid release tag")
    run(["/usr/bin/git", "ls-remote", "--exit-code", "--tags", REPOSITORY, f"refs/tags/{version}"], timeout=30)


def create_backup(version: str) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = BACKUPS / f"before-{version}-{timestamp}"
    target.mkdir(mode=0o700, parents=True)
    metadata = {
        "created_at": datetime.now(UTC).isoformat(),
        "target_version": version,
        "contents": ["PostgreSQL", "environment", "Nginx", "TLS"],
    }
    (target / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    with (target / "database.dump").open("wb") as stream:
        subprocess.run(
            ["/usr/sbin/runuser", "-u", "postgres", "--", "/usr/bin/pg_dump", "-Fc", "dashboardapi_ec"],
            check=True,
            stdout=stream,
            stderr=subprocess.PIPE,
            timeout=300,
        )
    for source, name in (
        (Path("/etc/dashboardapi-ec"), "dashboardapi-ec-etc"),
        (Path("/etc/nginx/sites-available/dashboardapi-ec"), "nginx-dashboardapi-ec.conf"),
    ):
        if source.is_dir():
            shutil.copytree(source, target / name, symlinks=True)
        elif source.is_file():
            shutil.copy2(source, target / name)
    return target


def wait_for_health() -> None:
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        connection = http.client.HTTPConnection("127.0.0.1", 8010, timeout=2)
        try:
            connection.request("GET", "/api/v1/health")
            if connection.getresponse().status == 200:
                return
        except OSError:
            pass
        finally:
            connection.close()
        time.sleep(1)
    raise RuntimeError("API health check did not recover")


def install(version: str) -> Path:
    verify_tag(version)
    backup = create_backup(version)
    rollback_package = installed_package()
    with tempfile.TemporaryDirectory(prefix="dashboardapi-update-", dir="/var/tmp") as temporary:
        source = Path(temporary) / "source"
        run(["/usr/bin/git", "clone", "--quiet", "--branch", version, "--depth", "1", REPOSITORY, str(source)], timeout=180)
        described = subprocess.run(
            ["/usr/bin/git", "-C", str(source), "describe", "--tags", "--exact-match"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout.strip()
        if described != version:
            raise RuntimeError("Downloaded source does not match release tag")
        project = source / "DashboardAPI-EC"
        run([str(project / "scripts" / "build-deb.sh")], cwd=project, timeout=1200)
        package_version = version.removeprefix("v").split("-", 1)[0]
        packages = list((project / "dist").glob(f"dashboardapi-ec_{package_version}_*.deb"))
        if len(packages) != 1:
            raise RuntimeError("Expected exactly one Debian package")
        PACKAGE_CACHE.mkdir(mode=0o700, parents=True, exist_ok=True)
        cached_package = PACKAGE_CACHE / packages[0].name
        shutil.copy2(packages[0], cached_package)
        try:
            run(
                ["/usr/bin/apt-get", "install", "--reinstall", "-y", str(cached_package)],
                timeout=600,
            )
            wait_for_health()
        except Exception:
            if rollback_package and rollback_package.exists():
                run(
                    [
                        "/usr/bin/apt-get",
                        "install",
                        "--reinstall",
                        "--allow-downgrades",
                        "-y",
                        str(rollback_package),
                    ],
                    timeout=600,
                )
                wait_for_health()
            raise
    return backup


def read_request() -> str | None:
    STATE.mkdir(mode=0o750, parents=True, exist_ok=True)
    directory = os.open(STATE, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        try:
            fd = os.open("request.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        except FileNotFoundError:
            return None
        with os.fdopen(fd, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError("Update request is not a regular file")
            raw = stream.read(4097)
            if len(raw) > 4096:
                raise ValueError("Update request is too large")
        os.unlink("request.json", dir_fd=directory)
        request = json.loads(raw)
        return str(request["version"])
    finally:
        os.close(directory)


def main() -> None:
    try:
        version = read_request()
    except Exception:
        write_status({"state": "error", "message": "La solicitud de actualización es inválida."})
        return
    if version is None:
        return
    write_status({"state": "running", "version": version, "message": "Creando respaldo y construyendo el paquete."})
    try:
        backup = install(version)
        write_status(
            {
                "state": "success",
                "version": version,
                "message": "Actualización completada y API verificada.",
                "backup": str(backup),
                "completed_at": datetime.now(UTC).isoformat(),
            }
        )
    except Exception:
        write_status(
            {
                "state": "error",
                "version": version,
                "message": "La actualización falló. Los datos y el respaldo previo se conservaron; revisa journalctl.",
            }
        )
        raise


if __name__ == "__main__":
    main()
