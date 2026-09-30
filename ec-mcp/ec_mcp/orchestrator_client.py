from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import httpx

from .compat import CompatibilityEngine, CompatibilityError, ResolvedOperation
from .config import Settings

logger = logging.getLogger("ec_mcp.orchestrator")


class OrchestratorClient:
    def __init__(self, settings: Settings, engine: CompatibilityEngine, client: httpx.Client | None = None):
        if not settings.orchestrator_url:
            raise ValueError("EC_ORCHESTRATOR_URL is not configured")
        self._settings = settings
        self._engine = engine
        self._cached_profile: str | None = None
        self._appliances_cache: list[dict[str, Any]] | None = None
        self._response_cache: dict[tuple, tuple[float, Any]] = {}
        self._cache_ttl = float(getattr(settings, "api_cache_ttl", 30.0))
        self._cache_max_entries = 128
        self._metrics: dict[str, dict[str, float]] = {}
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

    def metrics(self) -> dict[str, dict[str, float]]:
        return self._metrics

    def _record_metric(self, label: str, elapsed: float, size: int, cache_hit: bool) -> None:
        entry = self._metrics.setdefault(label, {"calls": 0.0, "total_time": 0.0, "max_time": 0.0, "total_bytes": 0.0, "cache_hits": 0.0})
        entry["calls"] += 1
        entry["total_time"] += elapsed
        entry["max_time"] = max(entry["max_time"], elapsed)
        entry["total_bytes"] += size
        if cache_hit:
            entry["cache_hits"] += 1
        logger.info(
            "op=%s elapsed=%.3fs bytes=%d cache=%s",
            label, elapsed, size, "hit" if cache_hit else "miss",
        )

    def _cache_key(self, path: str, query: dict[str, Any]) -> tuple:
        return (path, tuple(sorted((k, str(v)) for k, v in query.items() if v is not None)))

    def get_raw(self, path: str, **query: Any) -> Any:
        key = self._cache_key(path, query)
        now = time.monotonic()
        cached = self._response_cache.get(key)
        if cached is not None and now - cached[0] < self._cache_ttl:
            self._record_metric(path, 0.0, 0, cache_hit=True)
            return cached[1]
        started = time.monotonic()
        response = self._client.get(path, headers=self._headers(), params={k: v for k, v in query.items() if v is not None})
        elapsed = time.monotonic() - started
        self._record_metric(path, elapsed, len(response.content), cache_hit=False)
        if response.status_code >= 400:
            message = self._error_message(response, f"GET {path}")
            if response.status_code == 404:
                body = (response.text or "").strip()
                if any(marker in body for marker in ("No application groups configured", "no data", "not configured", "No configured")):
                    return {"data": None, "reason": "endpoint returned empty result (404 with empty-data semantics)"}
            raise RuntimeError(message)
        if not response.content:
            return {}
        try:
            data = response.json()
        except json.JSONDecodeError as error:
            raise RuntimeError(f"Orchestrator returned non-JSON response for GET {path}") from error
        if len(self._response_cache) >= self._cache_max_entries:
            oldest = min(self._response_cache, key=lambda k: self._response_cache[k][0])
            self._response_cache.pop(oldest, None)
        self._response_cache[key] = (time.monotonic(), data)
        return data

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
        cached = getattr(self, "_cached_profile", None)
        if cached:
            return cached
        detected = self.detect_version()
        matched = self._engine.match_version(detected)
        if matched is None:
            raise CompatibilityError(
                f"Orchestrator version {detected!r} does not match any loaded profile {self._engine.versions}"
            )
        self._cached_profile = matched
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
        label = f"{operation_id}"
        started = time.monotonic()
        response = self._client.request(
            resolved.method,
            f"{api_root}{resolved.path}",
            headers=self._headers(),
            params={k: v for k, v in query.items() if v is not None},
            json=json_body,
        )
        self._record_metric(label, time.monotonic() - started, len(response.content), cache_hit=False)
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
        if response.status_code == 400:
            hint = (" HTTP 400 = invalid or missing query parameters: check "
                    "param names/values (e.g. granularity=minute|hour|day, "
                    "start_time/end_time as epoch ms) via list_api_operations(search=...) "
                    "and request_echo.query_used.")
        elif response.status_code == 404:
            hint = " HTTP 404 = the endpoint does not exist on this Orchestrator version."
        elif response.status_code in (500, 502, 503):
            hint = (" HTTP 5xx = the Orchestrator could not serve the request; "
                    "if it mentions the appliance, it may not exist or be unreachable "
                    "(check reachability with list_appliances).")
        elif response.status_code == 401:
            hint = " HTTP 401 = authentication failed: check EC_ORCHESTRATOR_API_KEY or credentials."
        return f"Orchestrator returned HTTP {response.status_code} for {action}: {detail!r}.{hint}"

    def list_appliances(self, refresh: bool = False) -> list[dict[str, Any]]:
        if self._appliances_cache is not None and not refresh:
            return self._appliances_cache
        data: Any = None
        last_error: Exception | None = None
        for path in ("/appliance/approved", "/neStatus", "/appliance"):
            try:
                candidate = self.get_raw(path)
            except RuntimeError as error:
                last_error = error
                message = str(error)
                if "HTTP 404" not in message and "HTTP 405" not in message:
                    raise
                continue
            items = candidate
            if isinstance(candidate, dict):
                items = (
                    candidate.get("appliances")
                    or candidate.get("data")
                    or candidate.get("result")
                    or candidate.get("neStatus")
                    or []
                )
            if isinstance(items, list) and items:
                data = candidate
                break
            last_error = RuntimeError(f"GET {path}: empty inventory response")
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
                    "lan_ip": item.get("lanIp") or item.get("lanIPAddress") or item.get("dataIp"),
                    "wan_ips": [
                        value
                        for value in (
                            item.get("wanIp"),
                            item.get("wanIPAddress"),
                            item.get("wanIp2"),
                            item.get("wanIpAddress2"),
                            item.get("wanInterfaceIp"),
                            item.get("mgmtAddress"),
                        )
                        if value
                    ],
                }
            )
        self._appliances_cache = appliances
        return appliances

    def appliance_api_get(self, ne_pk: str, appliance_path: str, **query: Any) -> dict[str, Any]:
        if not appliance_path.startswith("/"):
            appliance_path = "/" + appliance_path
        return self.get_raw("/appliance/rest", nePk=ne_pk, url=appliance_path, **query)
