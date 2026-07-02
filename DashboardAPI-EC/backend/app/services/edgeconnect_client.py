import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import httpx

from app.compatibility.engine import CompatibilityEngine
from app.core.security import decrypt_secret
from app.models.orchestrator import Orchestrator


class EdgeConnectClientError(RuntimeError):
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        duration_ms: int | None = None,
        payload: dict | None = None,
        method: str = "GET",
        path: str = "unresolved",
    ):
        super().__init__(message)
        self.status_code = status_code
        self.duration_ms = duration_ms
        self.payload = payload or {}
        self.method = method
        self.path = path


@dataclass(frozen=True)
class EdgeConnectResponse:
    operation_id: str
    method: str
    path: str
    status_code: int
    duration_ms: int
    payload: dict


class EdgeConnectClient:
    def __init__(self, orchestrator: Orchestrator, engine: CompatibilityEngine):
        self.orchestrator = orchestrator
        self.engine = engine

    def call_operation(
        self,
        version: str,
        operation_id: str,
        path_params: dict[str, str] | None = None,
    ) -> EdgeConnectResponse:
        operation = self.engine.resolve(version, operation_id, path_params)
        url = urljoin(f"{self.orchestrator.base_url.rstrip('/')}/", operation.path.lstrip("/"))
        headers = self._headers()
        auth = self._auth()
        started = time.perf_counter()

        try:
            with httpx.Client(
                verify=self.orchestrator.verify_tls,
                timeout=self.orchestrator.timeout_seconds,
                follow_redirects=True,
            ) as client:
                response = client.request(operation.method, url, headers=headers, auth=auth)
        except httpx.HTTPError as exc:
            duration = int((time.perf_counter() - started) * 1000)
            raise EdgeConnectClientError(
                str(exc),
                duration_ms=duration,
                method=operation.method,
                path=operation.path,
            ) from exc

        duration = int((time.perf_counter() - started) * 1000)
        payload = self._payload(response)
        if response.is_error:
            raise EdgeConnectClientError(
                f"EdgeConnect API returned HTTP {response.status_code}",
                status_code=response.status_code,
                duration_ms=duration,
                payload=payload,
                method=operation.method,
                path=operation.path,
            )

        return EdgeConnectResponse(
            operation_id=operation_id,
            method=operation.method,
            path=operation.path,
            status_code=response.status_code,
            duration_ms=duration,
            payload=payload,
        )

    def detect_version(self) -> EdgeConnectResponse:
        candidates = [self.orchestrator.api_version] if self.orchestrator.api_version else []
        candidates.extend(version for version in reversed(self.engine.versions) if version not in candidates)
        last_error: EdgeConnectClientError | None = None
        for version in candidates:
            if not version:
                continue
            try:
                return self.call_operation(version, "orchestrator.version")
            except EdgeConnectClientError as exc:
                last_error = exc
        raise last_error or EdgeConnectClientError("No compatible version endpoint is available")

    def _headers(self) -> dict[str, str]:
        token = decrypt_secret(self.orchestrator.encrypted_api_token)
        if self.orchestrator.auth_type == "bearer" and token:
            return {"Authorization": f"Bearer {token}"}
        if self.orchestrator.auth_type == "api_key" and token:
            return {self.orchestrator.api_key_header or "X-API-Key": token}
        return {}

    def _auth(self) -> tuple[str, str] | None:
        if self.orchestrator.auth_type != "basic":
            return None
        password = decrypt_secret(self.orchestrator.encrypted_password)
        if self.orchestrator.username and password:
            return (self.orchestrator.username, password)
        return None

    @staticmethod
    def _payload(response: httpx.Response) -> dict[str, Any]:
        content_type = response.headers.get("content-type", "")
        if "json" in content_type:
            data = response.json()
            return data if isinstance(data, dict) else {"items": data}
        text = response.text.strip()
        return {"raw": text[:20000]}
