"""Multi-target credential registry for ec-mcp.

Stores named EdgeConnect Orchestrators and SSE platforms (Axis Security)
independently in a JSON file (0600). The admin web UI manages this registry;
the runtime resolves a target by name and builds per-target clients.

Two storage formats are supported:

- Registry JSON (``EC_ADMIN_STORE``, default ``.ec-admin.json``) with keys
  ``orchestrators`` and ``sse_platforms``. This is what the admin UI reads and
  writes; it is the source of truth for "apply".
- Environment JSON blobs for the runtime process:
  ``EC_ORCHESTRATORS_JSON`` and ``EC_SSE_PLATFORMS_JSON``. Each is a JSON object
  mapping target name to its settings. When present, the runtime loads all
  targets from it. When absent, the runtime falls back to the single-target
  ``EC_ORCHESTRATOR_*`` / ``EC_AXIS_*`` variables (backwards compatible).

Secrets are never returned by the admin API; the UI only reports whether a
secret is configured.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ORCHESTRATOR_FIELDS = (
    "url",
    "api_key",
    "username",
    "password",
    "verify_tls",
    "ssh_user",
    "ssh_password",
    "ssh_enable_password",
    "ssh_host",
)

SSE_FIELDS = (
    "provider",
    "base_url",
    "admin_token",
    "verify_tls",
    "timeout",
)

SECRET_ORCHESTRATOR_FIELDS = {"api_key", "password", "ssh_password", "ssh_enable_password"}
SECRET_SSE_FIELDS = {"admin_token"}


class RegistryError(ValueError):
    pass


@dataclass(frozen=True)
class OrchestratorTarget:
    name: str
    url: str = ""
    api_key: str = ""
    username: str = ""
    password: str = ""
    verify_tls: bool = True
    ssh_user: str = ""
    ssh_password: str = ""
    ssh_enable_password: str = ""
    ssh_host: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SseTarget:
    name: str
    provider: str = "axis"
    base_url: str = ""
    admin_token: str = ""
    verify_tls: bool = True
    timeout: float = 30.0
    extra: dict[str, Any] = field(default_factory=dict)


def _validate_url(value: str, *, field_name: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RegistryError(f"{field_name}: URL inválida")
    return value.rstrip("/")


def _validate_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise RegistryError("El nombre es obligatorio")
    if any(character.isspace() for character in name) or any(c in name for c in "\"'\\\n\r\x00"):
        raise RegistryError("El nombre no puede contener espacios ni comillas")
    return name


def _clean_entry(entry: dict[str, Any], allowed: tuple[str, ...]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in entry.items():
        if key not in allowed:
            continue
        if isinstance(value, str):
            value = value.strip()
            if "\n" in value or "\r" in value or "\x00" in value:
                raise RegistryError(f"El campo '{key}' contiene caracteres no permitidos")
        cleaned[key] = value
    return cleaned


def _to_bool(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"true", "1", "yes", "on"}


def _to_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def orchestrator_from_entry(name: str, entry: dict[str, Any]) -> OrchestratorTarget:
    entry = _clean_entry(entry, ORCHESTRATOR_FIELDS)
    url = str(entry.get("url") or "")
    if url:
        url = _validate_url(url, field_name="url")
    if not url:
        raise RegistryError("La URL del Orchestrator es obligatoria")
    if not (entry.get("api_key") or entry.get("username")):
        raise RegistryError("Configura API key o usuario/contraseña")
    ssh_host = str(entry.get("ssh_host") or "")
    return OrchestratorTarget(
        name=name,
        url=url,
        api_key=str(entry.get("api_key") or ""),
        username=str(entry.get("username") or ""),
        password=str(entry.get("password") or ""),
        verify_tls=_to_bool(entry.get("verify_tls"), True),
        ssh_user=str(entry.get("ssh_user") or ""),
        ssh_password=str(entry.get("ssh_password") or ""),
        ssh_enable_password=str(entry.get("ssh_enable_password") or ""),
        ssh_host=ssh_host,
    )


def sse_from_entry(name: str, entry: dict[str, Any]) -> SseTarget:
    entry = _clean_entry(entry, SSE_FIELDS)
    provider = str(entry.get("provider") or "axis").strip().lower() or "axis"
    base_url = str(entry.get("base_url") or "")
    if base_url:
        base_url = _validate_url(base_url, field_name="base_url")
    if not base_url:
        raise RegistryError("La URL base de la plataforma SSE es obligatoria")
    if not entry.get("admin_token"):
        raise RegistryError("El token de administración es obligatorio")
    return SseTarget(
        name=name,
        provider=provider,
        base_url=base_url,
        admin_token=str(entry.get("admin_token") or ""),
        verify_tls=_to_bool(entry.get("verify_tls"), True),
        timeout=_to_float(entry.get("timeout"), 30.0),
    )


def public_orchestrator(name: str, entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "url": entry.get("url", ""),
        "verify_tls": _to_bool(entry.get("verify_tls"), True),
        "has_api_key": bool(entry.get("api_key")),
        "has_password": bool(entry.get("password")),
        "username": entry.get("username", ""),
        "ssh_user": entry.get("ssh_user", ""),
        "ssh_host": entry.get("ssh_host", ""),
        "has_ssh_password": bool(entry.get("ssh_password")),
        "has_enable_password": bool(entry.get("ssh_enable_password")),
    }


def public_sse(name: str, entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "provider": entry.get("provider", "axis"),
        "base_url": entry.get("base_url", ""),
        "verify_tls": _to_bool(entry.get("verify_tls"), True),
        "timeout": _to_float(entry.get("timeout"), 30.0),
        "has_admin_token": bool(entry.get("admin_token")),
    }


class TargetRegistry:
    """JSON-backed registry of Orchestrators and SSE platforms."""

    def __init__(self, path: Path):
        self._path = Path(path)

    def _load(self) -> dict[str, dict[str, dict[str, Any]]]:
        if not self._path.is_file():
            return {"orchestrators": {}, "sse_platforms": {}}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"orchestrators": {}, "sse_platforms": {}}
        if not isinstance(data, dict):
            return {"orchestrators": {}, "sse_platforms": {}}
        data.setdefault("orchestrators", {})
        data.setdefault("sse_platforms", {})
        return data

    def _save(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        self._path.chmod(0o600)

    def list_orchestrators(self) -> dict[str, dict[str, Any]]:
        return dict(self._load()["orchestrators"])

    def list_sse(self) -> dict[str, dict[str, Any]]:
        return dict(self._load()["sse_platforms"])

    def get_orchestrator(self, name: str) -> dict[str, Any]:
        return dict(self._load()["orchestrators"].get(name, {}))

    def get_sse(self, name: str) -> dict[str, Any]:
        return dict(self._load()["sse_platforms"].get(name, {}))

    def save_orchestrator(self, name: str, entry: dict[str, Any], *, partial: bool = True) -> dict[str, Any]:
        name = _validate_name(name)
        data = self._load()
        existing = data["orchestrators"].get(name, {}) if partial else {}
        merged = {**existing, **_clean_entry(entry, ORCHESTRATOR_FIELDS)}
        # Empty strings on secret fields mean "keep existing"; explicit null clears.
        for field_name in SECRET_ORCHESTRATOR_FIELDS:
            if field_name in entry:
                if entry[field_name] is None or str(entry[field_name]).strip() == "":
                    merged.pop(field_name, None)
        if not partial:
            for field_name in SECRET_ORCHESTRATOR_FIELDS:
                if field_name not in entry:
                    merged.pop(field_name, None)
        if partial:
            # En actualización parcial, los secretos vacíos heredan el valor existente.
            for field_name in SECRET_ORCHESTRATOR_FIELDS:
                if field_name in entry and (entry[field_name] is None or str(entry[field_name]).strip() == ""):
                    if field_name in existing:
                        merged[field_name] = existing[field_name]
        orchestrator_from_entry(name, merged)  # validates
        data["orchestrators"][name] = merged
        self._save(data)
        return merged

    def delete_orchestrator(self, name: str) -> bool:
        data = self._load()
        if name in data["orchestrators"]:
            del data["orchestrators"][name]
            self._save(data)
            return True
        return False

    def _rename(self, section: str, old: str, new: str) -> dict[str, Any]:
        new = _validate_name(new)
        data = self._load()
        if old not in data[section]:
            raise RegistryError(f"No existe '{old}'")
        if new != old and new in data[section]:
            raise RegistryError(f"Ya existe '{new}'")
        data[section][new] = data[section].pop(old)
        self._save(data)
        return data[section][new]

    def _duplicate(self, section: str, name: str, new: str) -> dict[str, Any]:
        new = _validate_name(new)
        data = self._load()
        if name not in data[section]:
            raise RegistryError(f"No existe '{name}'")
        if new in data[section]:
            raise RegistryError(f"Ya existe '{new}'")
        data[section][new] = dict(data[section][name])
        self._save(data)
        return data[section][new]

    def rename_orchestrator(self, old: str, new: str) -> dict[str, Any]:
        return self._rename("orchestrators", old, new)

    def duplicate_orchestrator(self, name: str, new: str) -> dict[str, Any]:
        return self._duplicate("orchestrators", name, new)

    def rename_sse(self, old: str, new: str) -> dict[str, Any]:
        return self._rename("sse_platforms", old, new)

    def duplicate_sse(self, name: str, new: str) -> dict[str, Any]:
        return self._duplicate("sse_platforms", name, new)

    def save_sse(self, name: str, entry: dict[str, Any], *, partial: bool = True) -> dict[str, Any]:
        name = _validate_name(name)
        data = self._load()
        existing = data["sse_platforms"].get(name, {}) if partial else {}
        merged = {**existing, **_clean_entry(entry, SSE_FIELDS)}
        if "admin_token" in entry and (entry["admin_token"] is None or str(entry["admin_token"]).strip() == ""):
            merged.pop("admin_token", None)
            if partial and "admin_token" in existing:
                merged["admin_token"] = existing["admin_token"]
        if not partial and "admin_token" not in entry:
            merged.pop("admin_token", None)
        sse_from_entry(name, merged)  # validates
        data["sse_platforms"][name] = merged
        self._save(data)
        return merged

    def delete_sse(self, name: str) -> bool:
        data = self._load()
        if name in data["sse_platforms"]:
            del data["sse_platforms"][name]
            self._save(data)
            return True
        return False

    def to_env_blob(self) -> dict[str, str]:
        """Render the registry as EC_ORCHESTRATORS_JSON / EC_SSE_PLATFORMS_JSON."""
        data = self._load()
        blob: dict[str, str] = {}
        if data["orchestrators"]:
            blob["EC_ORCHESTRATORS_JSON"] = json.dumps(data["orchestrators"], separators=(",", ":"))
        if data["sse_platforms"]:
            blob["EC_SSE_PLATFORMS_JSON"] = json.dumps(data["sse_platforms"], separators=(",", ":"))
        return blob


def resolve_default_name(names, explicit: str = "") -> str:
    """Resolve the default target name: explicit name, else 'default', else first sorted."""
    ordered = sorted(names)
    explicit = (explicit or "").strip()
    if explicit and explicit in ordered:
        return explicit
    if "default" in ordered:
        return "default"
    return ordered[0] if ordered else ""

def _parse_env_json_blob(name: str, blob: str = "") -> dict[str, dict[str, Any]]:
    raw = blob.strip() or os.environ.get(name, "")
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RegistryError(f"{name} no es un JSON válido: {error}") from error
    if not isinstance(data, dict):
        raise RegistryError(f"{name} debe ser un objeto JSON nombre -> configuración")
    return data


def _parse_env_json(name: str) -> dict[str, dict[str, Any]]:
    raw = os.environ.get(name, "")
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RegistryError(f"{name} no es un JSON válido: {error}") from error
    if not isinstance(data, dict):
        raise RegistryError(f"{name} debe ser un objeto JSON nombre -> configuración")
    return data


def load_orchestrators_from_env(blob: str = "") -> dict[str, OrchestratorTarget]:
    """Load all Orchestrator targets from EC_ORCHESTRATORS_JSON (or an explicit blob)."""
    raw = _parse_env_json_blob("EC_ORCHESTRATORS_JSON", blob)
    targets: dict[str, OrchestratorTarget] = {}
    for name, entry in raw.items():
        if not isinstance(entry, dict):
            raise RegistryError(f"EC_ORCHESTRATORS_JSON[{name}] debe ser un objeto")
        targets[_validate_name(str(name))] = orchestrator_from_entry(str(name), entry)
    return targets


def load_sse_from_env(blob: str = "") -> dict[str, SseTarget]:
    """Load all SSE platform targets from EC_SSE_PLATFORMS_JSON (or an explicit blob)."""
    raw = _parse_env_json_blob("EC_SSE_PLATFORMS_JSON", blob)
    targets: dict[str, SseTarget] = {}
    for name, entry in raw.items():
        if not isinstance(entry, dict):
            raise RegistryError(f"EC_SSE_PLATFORMS_JSON[{name}] debe ser un objeto")
        targets[_validate_name(str(name))] = sse_from_entry(str(name), entry)
    return targets


def registry_path() -> Path:
    return Path(os.environ.get("EC_ADMIN_STORE") or Path.cwd() / ".ec-admin.json")


def load_registry() -> TargetRegistry:
    return TargetRegistry(registry_path())
