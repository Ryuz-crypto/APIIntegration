from __future__ import annotations

import json
from typing import Any

import httpx

from .compat import CompatibilityEngine, CompatibilityError, ResolvedOperation
from .config import Settings


class OrchestratorClient:
    def __init__(self, settings: Settings, engine: CompatibilityEngine, client: httpx.Client | None = None):
        if not settings.orchestrator_url:
            raise ValueError("EC_ORCHESTRATOR_URL is not configured")
        self._settings = settings
        self._engine = engine
        self._client = client or httpx.Client(
            base_url=settings.orchestrator_url,
            verify=settings.verify_tls,
            timeout=30.0,
        )
        self._api_key = settings.orchestrator_api_key
        if not self._api_key:
            username, password = settings.orchestrator_username, settings.orchestrator_password
            if not username:
                raise ValueError("Either EC_ORCHESTRATOR_API_KEY or EC_ORCHESTRATOR_USER is required")
            self._api_key = self._login(username, password)

    def close(self) -> None:
        self._client.close()

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    def _login(self, username: str, password: str) -> str:
        response = self._client.post(
            "/gms/rest/authentication/login",
            json={"user": username, "password": password},
        )
        response.raise_for_status()
        return response.json().get("sessionCookie") or response.json().get("token") or response.text

    def detect_version(self) -> str | None:
        try:
            response = self._client.get("/gms/rest/gmsserver/briefInfo")
            if response.status_code != 200:
                return None
            info = response.json()
            version = info.get("version") or info.get("softwareVersion")
            if isinstance(version, str):
                return version
        except (httpx.HTTPError, json.JSONDecodeError):
            return None
        return None

    def resolve_active_profile(self) -> str:
        detected = self.detect_version()
        matched = self._engine.match_version(detected)
        if matched is None:
            raise CompatibilityError(
                f"Orchestrator version {detected!r} does not match any loaded profile {self._engine.versions}"
            )
        return matched

    def call(
        self,
        version: str,
        operation_id: str,
        path_params: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
        **query: Any,
    ) -> dict[str, Any]:
        resolved: ResolvedOperation = self._engine.resolve(version, operation_id, path_params)
        api_root = self._profile_api_root(version)
        response = self._client.request(
            resolved.method,
            f"{api_root}{resolved.path}",
            headers=self._headers(),
            params={k: v for k, v in query.items() if v is not None},
            json=json_body,
        )
        response.raise_for_status()
        if not response.content:
            return {"ok": True}
        return response.json()

    def _profile_api_root(self, version: str) -> str:
        profile = getattr(self._engine, "_profiles", {}).get(version, {})
        return profile.get("api_root", "/gms/rest")
