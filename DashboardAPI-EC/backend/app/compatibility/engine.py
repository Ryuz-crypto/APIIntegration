from dataclasses import dataclass
import re


class CompatibilityError(ValueError):
    pass


@dataclass(frozen=True)
class ResolvedOperation:
    version: str
    operation_id: str
    method: str
    path: str
    polling_hint_seconds: int | None = None
    notes: tuple[str, ...] = ()


class CompatibilityEngine:
    def __init__(self, profiles: list[dict]):
        self._profiles = {profile["version"]: profile for profile in profiles}

    @property
    def versions(self) -> list[str]:
        return sorted(self._profiles)

    def list_operations(self, version: str) -> list[str]:
        profile = self._get_profile(version)
        return sorted(profile.get("operations", {}))

    def resolve(
        self,
        version: str,
        operation_id: str,
        path_params: dict[str, str] | None = None,
    ) -> ResolvedOperation:
        profile = self._get_profile(version)
        operations = profile.get("operations", {})
        operation = operations.get(operation_id)
        if operation is None:
            raise CompatibilityError(f"Operation '{operation_id}' is not available in API {version}")

        path = operation["path"]
        for key, value in (path_params or {}).items():
            path = path.replace("{" + key + "}", value)

        unresolved = sorted(set(re.findall(r"{([^{}]+)}", path)))
        if unresolved:
            raise CompatibilityError(f"Missing path params: {', '.join(unresolved)}")

        return ResolvedOperation(
            version=version,
            operation_id=operation_id,
            method=operation["method"].upper(),
            path=f"{profile.get('api_root', '').rstrip('/')}/{path.lstrip('/')}",
            polling_hint_seconds=operation.get("polling_hint_seconds"),
            notes=tuple(operation.get("notes", [])),
        )

    def _get_profile(self, version: str) -> dict:
        profile = self._profiles.get(version)
        if profile is None:
            raise CompatibilityError(f"No compatibility profile found for API {version}")
        return profile
