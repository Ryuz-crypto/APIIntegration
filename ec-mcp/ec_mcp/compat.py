from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote


class CompatibilityError(ValueError):
    pass


# The vendor exposes this mutation as GET. HTTP method alone is not a permission.
SIDE_EFFECTING_GET_PATHS = {"/ids/updateSignatureFromPortal"}


def is_read_only_operation(operation: dict[str, Any]) -> bool:
    path = operation["path"].split("?", 1)[0]
    for prefix in ("/gms/rest", "/rest/json"):
        path = path.removeprefix(prefix)
    return (
        operation["method"].upper() in {"GET", "HEAD"}
        and operation.get("risk") not in {"write", "dangerous"}
        and path not in SIDE_EFFECTING_GET_PATHS
    )


@dataclass(frozen=True)
class ResolvedOperation:
    version: str
    operation_id: str
    method: str
    path: str
    polling_hint_seconds: int | None = None


class CompatibilityEngine:
    def __init__(self, profiles: list[dict[str, Any]]):
        self._profiles = {profile["version"]: profile for profile in profiles}

    @property
    def versions(self) -> list[str]:
        return sorted(self._profiles)

    def match_version(self, detected: str | None) -> str | None:
        if not detected:
            return None
        if detected in self._profiles:
            return detected
        parts = detected.split(".")
        if len(parts) >= 2:
            major_minor = ".".join(parts[:2])
            if major_minor in self._profiles:
                return major_minor
            if major_minor == "9.7" and "9.6" in self._profiles:
                return "9.6"
        return None

    def resolve(self, version: str, operation_id: str, path_params: dict[str, str] | None = None) -> ResolvedOperation:
        profile = self._profiles.get(version)
        if profile is None:
            raise CompatibilityError(f"No profile for API version {version}")
        operation = profile.get("operations", {}).get(operation_id)
        if operation is None:
            raise CompatibilityError(f"Operation '{operation_id}' is not available in API {version}")
        path = operation["path"]
        path = path.split("?", 1)[0]
        if path_params is not None:
            path = render_path(path, path_params)
        return ResolvedOperation(
            version=version,
            operation_id=operation_id,
            method=operation["method"].upper(),
            path=path,
            polling_hint_seconds=operation.get("polling_hint_seconds"),
        )


def load_profiles(profiles_dir: Path) -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    for path in sorted(Path(profiles_dir).glob("edgeconnect-*.json")):
        with path.open(encoding="utf-8") as profile_file:
            profiles.append(json.load(profile_file))
    if not profiles:
        raise CompatibilityError(f"No EdgeConnect profiles found in {profiles_dir}")
    return profiles


def render_path(path: str, params: dict[str, str]) -> str:
    """Render OAS and Postman placeholders without allowing route injection."""

    def replace(match: re.Match) -> str:
        key = match.group(1) or match.group(2)
        if key not in params or params[key] is None or str(params[key]) == "":
            raise CompatibilityError(f"Missing path parameter '{key}'")
        value = str(params[key])
        if value in {".", ".."} or re.search(r"[/\\?#%\x00-\x1f\x7f]", value):
            raise CompatibilityError(f"Unsafe path parameter '{key}'")
        return quote(value, safe="")

    return re.sub(r"\{([^}]+)\}|(?<=/):([A-Za-z_][A-Za-z0-9_]*)", replace, path)
