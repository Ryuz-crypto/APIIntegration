from __future__ import annotations

import json
import re
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
        return {"X-Auth-Token": self._api_key}

    def _login(self, username: str, password: str) -> str:
        response = self._client.post(
            "/gms/rest/authentication/login",
            json={"user": username, "password": password},
        )
        response.raise_for_status()
        return response.json().get("sessionCookie") or response.json().get("token") or response.text

    def detect_version(self) -> str | None:
        try:
            response = self._client.get("/gms/rest/gmsserver/briefInfo", headers=self._headers())
            if response.status_code != 200:
                return None
            info = response.json()
            version = info.get("version") or info.get("softwareVersion") or info.get("release")
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
        if response.status_code >= 400:
            raise RuntimeError(
                self._error_message(response, f"{resolved.method} {api_root}{resolved.path}")
            )
        if not response.content:
            return {"ok": True}
        return response.json()

    def _profile_api_root(self, version: str) -> str:
        profile = getattr(self._engine, "_profiles", {}).get(version, {})
        return profile.get("api_root", "/gms/rest")

    def _error_message(self, response: httpx.Response, action: str) -> str:
        detail = ""
        content_type = response.headers.get("content-type", "")
        if "json" in content_type:
            try:
                body = response.json()
                detail = str(body.get("message") or body.get("error") or body)[:300]
            except Exception:
                detail = response.text[:300]
        else:
            detail = re.sub(r"<[^>]+>", " ", response.text or "")
            detail = " ".join(detail.split())[:300]
        hint = ""
        if response.status_code == 404:
            hint = " The endpoint does not exist on this Orchestrator version."
        elif response.status_code in (400, 500) and "nePk" in response.request.url.params:
            hint = " The appliance may not exist or may be unreachable from the Orchestrator."
        return f"Orchestrator returned HTTP {response.status_code} for {action}: {detail!r}.{hint}"

    def list_appliances(self) -> list[dict[str, Any]]:
        data: Any = None
        last_error: Exception | None = None
        for path in ("/appliance/approved", "/neStatus", "/appliance"):
            try:
                data = self.get_raw(path)
                break
            except httpx.HTTPError as error:
                last_error = error
                if isinstance(error, httpx.HTTPStatusError) and error.response.status_code not in (404, 405):
                    raise RuntimeError(self._error_message(error.response, f"GET {path}")) from error
        if data is None:
            raise RuntimeError(
                f"Could not fetch the appliance inventory from the Orchestrator: {last_error}"
            )
        if isinstance(data, dict):
            data = (
                data.get("appliances")
                or data.get("data")
                or data.get("result")
                or data.get("neStatus")
                or []
            )
        appliances = []
        for item in data or []:
            if not isinstance(item, dict):
                continue
            appliances.append(
                {
                    "nePk": item.get("nePk") or item.get("nePK") or item.get("id"),
                    "name": item.get("name") or item.get("hostname") or item.get("dnsName"),
                    "model": item.get("model") or item.get("modelNumber"),
                    "serial_number": item.get("serialNumber") or item.get("serial"),
                    "software_version": item.get("softwareVersion") or item.get("currentSoftwareVersion"),
                    "ip": item.get("ipAddress") or item.get("managementIp") or item.get("ip"),
                    "site": item.get("site") or item.get("location") or item.get("siteName"),
                    "state": item.get("state") or item.get("adminState"),
                    "reachability": item.get("reachability") or item.get("neState"),
                }
            )
        return appliances

    def appliance_api_get(self, ne_pk: str, appliance_path: str, **query: Any) -> dict[str, Any]:
        if not appliance_path.startswith("/"):
            appliance_path = "/" + appliance_path
        return self.get_raw("/appliance/rest", nePk=ne_pk, url=appliance_path, **query)
