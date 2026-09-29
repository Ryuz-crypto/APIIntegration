from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class CompatibilityError(ValueError):
    pass


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
        for key, value in (path_params or {}).items():
            path = path.replace("{" + key + "}", str(value))
        path = path.split("?", 1)[0]
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
    rendered = path
    for key, value in params.items():
        rendered = rendered.replace("{" + key + "}", str(value))
    if re.search(r"\{[^}]+\}", rendered):
        raise CompatibilityError(f"Missing path parameters in {rendered}")
    return rendered
