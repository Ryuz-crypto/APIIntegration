import json
import os
import re
import secrets
from pathlib import Path

import httpx

from app.core.config import settings

TAG_PATTERN = re.compile(r"^v(\d+)\.(\d+)\.(\d+)-(stable|beta)$")
MAX_RELEASES = 20


def release_key(tag: str) -> tuple[int, int, int, int]:
    match = TAG_PATTERN.fullmatch(tag)
    if not match:
        return (0, 0, 0, 0)
    channel = 0 if match.group(4) == "stable" else -1
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)), channel)


def current_release() -> str:
    try:
        loaded = json.loads(
            (Path(settings.update_state_dir) / "status.json").read_text(encoding="utf-8")
        )
        version = str(loaded.get("version", ""))
        if loaded.get("state") == "success" and TAG_PATTERN.fullmatch(version):
            return version
    except (FileNotFoundError, json.JSONDecodeError, OSError, AttributeError):
        pass
    base = settings.app_version.split("-", 1)[0]
    channel = "beta" if "beta" in settings.app_version else "stable"
    return f"v{base}-{channel}"


def release_status() -> dict:
    current = settings.app_version
    installed_release = current_release()
    try:
        response = httpx.get(
            f"https://api.github.com/repos/{settings.update_repository}/tags",
            params={"per_page": 100},
            headers={"Accept": "application/vnd.github+json", "User-Agent": "DashboardAPI-EC"},
            timeout=15,
            follow_redirects=False,
        )
        response.raise_for_status()
        tags = sorted(
            {
                item.get("name", "")
                for item in response.json()
                if isinstance(item, dict) and TAG_PATTERN.fullmatch(str(item.get("name", "")))
            },
            key=release_key,
            reverse=True,
        )
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        return {
            "ok": False,
            "current": current,
            "current_release": installed_release,
            "latest": "",
            "latest_stable": "",
            "latest_beta": "",
            "update_available": False,
            "releases": [],
            "error": f"No se pudo consultar el canal oficial: {type(exc).__name__}.",
        }
    stable = next((tag for tag in tags if tag.endswith("-stable")), "")
    beta = next((tag for tag in tags if tag.endswith("-beta")), "")
    latest = tags[0] if tags else ""
    current_key = release_key(installed_release)
    return {
        "ok": True,
        "current": current,
        "current_release": installed_release,
        "latest": latest,
        "latest_stable": stable,
        "latest_beta": beta,
        "update_available": bool(latest and release_key(latest) > current_key),
        "releases": tags[:MAX_RELEASES],
    }


def update_status() -> dict:
    directory = Path(settings.update_state_dir)
    result = {"state": "idle", "current": settings.app_version}
    try:
        loaded = json.loads((directory / "status.json").read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            result.update(loaded)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    if (directory / "request.json").exists() and result.get("state") != "running":
        result.update({"state": "pending", "message": "Actualización en espera del servicio Ubuntu."})
    return result


def queue_update(version: str) -> dict:
    if not TAG_PATTERN.fullmatch(version):
        raise ValueError("Etiqueta de versión no permitida.")
    releases = release_status()
    if not releases.get("ok") or version not in releases.get("releases", []):
        raise ValueError("La versión no existe entre las etiquetas oficiales publicadas.")
    if release_key(version) <= release_key(current_release()):
        raise ValueError("Selecciona una versión posterior a la instalada.")
    directory = Path(settings.update_state_dir)
    directory.mkdir(mode=0o750, parents=True, exist_ok=True)
    temporary = directory / f"request-{secrets.token_hex(16)}"
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            os.chmod(temporary, 0o600)
            json.dump({"version": version}, stream)
        os.link(temporary, directory / "request.json")
    except FileExistsError:
        raise ValueError("Ya existe una actualización pendiente.") from None
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "state": "pending",
        "version": version,
        "message": "Actualización validada y programada. El dashboard se reiniciará.",
    }
