import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from app.compatibility.engine import CompatibilityEngine
from app.core.security import decrypt_secret
from app.models.orchestrator import Orchestrator
from app.services import interactive_auth


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
    def __init__(
        self,
        orchestrator: Orchestrator,
        engine: CompatibilityEngine,
        otp: str | None = None,
    ):
        self.orchestrator = orchestrator
        self.engine = engine
        self.otp = otp

    def call_operation(
        self,
        version: str,
        operation_id: str,
        path_params: dict[str, str] | None = None,
    ) -> EdgeConnectResponse:
        operation = self.engine.resolve(version, operation_id, path_params)
        url = self._url(operation.path)
        headers = self._headers()
        auth = self._auth()
        started = time.perf_counter()

        try:
            with httpx.Client(
                verify=self.orchestrator.verify_tls,
                timeout=self.orchestrator.timeout_seconds,
                follow_redirects=False,
            ) as client:
                if self.orchestrator.auth_type == "session_otp":
                    try:
                        cookies = interactive_auth.load(
                            interactive_auth.active_key(self.orchestrator), self.orchestrator
                        )
                    except interactive_auth.InteractiveAuthError as exc:
                        raise EdgeConnectClientError(str(exc), path=operation.path) from None
                    interactive_auth.restore_cookies(client, cookies)
                    self._csrf(client, headers)
                elif self.orchestrator.auth_type == "session":
                    self._login(client, headers)
                response = client.request(operation.method, url, headers=headers, auth=auth)
                if self.orchestrator.auth_type == "session":
                    self._logout(client, headers)
                if self.orchestrator.auth_type == "session_otp" and response.status_code in {
                    401,
                    403,
                }:
                    interactive_auth.invalidate(self.orchestrator)
        except interactive_auth.InteractiveAuthError as exc:
            raise EdgeConnectClientError(
                str(exc), method=operation.method, path=operation.path
            ) from None
        except httpx.HTTPError as exc:
            duration = int((time.perf_counter() - started) * 1000)
            raise EdgeConnectClientError(
                str(exc), duration_ms=duration, method=operation.method, path=operation.path
            ) from exc

        duration = int((time.perf_counter() - started) * 1000)
        payload = self._payload(response)
        if response.is_error or response.is_redirect:
            raise EdgeConnectClientError(
                f"{operation.method} {operation.path}: HTTP {response.status_code}. "
                + (
                    "Ruta API no encontrada; revisa la URL del Orchestrator y el perfil Swagger."
                    if response.status_code == 404
                    else "Revisa permisos y autenticación; si usas MFA, vuelve a iniciar sesión."
                ),
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
        candidates.extend(
            version for version in reversed(self.engine.versions) if version not in candidates
        )
        last_error: EdgeConnectClientError | None = None
        attempted_paths: set[tuple[str, str]] = set()
        for version in candidates:
            if not version:
                continue
            try:
                operation = self.engine.resolve(version, "orchestrator.version")
                signature = (operation.method, operation.path)
                if signature in attempted_paths:
                    continue
                attempted_paths.add(signature)
                return self.call_operation(version, "orchestrator.version")
            except EdgeConnectClientError as exc:
                last_error = exc
                if exc.status_code != 404 or exc.method == "POST":
                    raise
        raise last_error or EdgeConnectClientError("No compatible version endpoint is available")

    def _headers(self) -> dict[str, str]:
        token = decrypt_secret(self.orchestrator.encrypted_api_token)
        if self.orchestrator.auth_type == "bearer" and token:
            return {"Authorization": f"Bearer {token}"}
        if self.orchestrator.auth_type == "api_key" and token:
            return {self.orchestrator.api_key_header or "X-Auth-Token": token}
        return {}

    def _auth(self) -> tuple[str, str] | None:
        if self.orchestrator.auth_type != "basic":
            return None
        password = decrypt_secret(self.orchestrator.encrypted_password)
        if self.orchestrator.username and password:
            return (self.orchestrator.username, password)
        return None

    def _url(self, path: str) -> str:
        base = self.orchestrator.base_url.rstrip("/")
        if base.endswith("/gms/rest") and path.startswith("/gms/rest/"):
            return f"{base}{path.removeprefix('/gms/rest')}"
        if urlsplit(base).path not in {"", "/"}:
            parts = urlsplit(base)
            origin = urlunsplit((parts.scheme, parts.netloc, "/", "", ""))
            return urljoin(origin, path.lstrip("/"))
        return urljoin(f"{base}/", path.lstrip("/"))

    def _login(self, client: httpx.Client, headers: dict[str, str]) -> None:
        password = decrypt_secret(self.orchestrator.encrypted_password)
        if not self.orchestrator.username or not password:
            raise EdgeConnectClientError(
                "Session authentication requires username and password",
                method="POST",
                path="/gms/rest/authentication/login",
            )
        if self.orchestrator.auth_type == "session_otp" and not self.otp:
            raise EdgeConnectClientError(
                "This Orchestrator requires a one-time authentication code",
                method="POST",
                path="/gms/rest/authentication/login",
            )
        path = "/gms/rest/authentication/login?source=dashboardapi_ec"
        response = client.post(
            self._url(path),
            json={
                "user": self.orchestrator.username,
                "password": password,
                "token": self.otp or "",
                "loginType": self.orchestrator.login_type,
            },
            headers=headers,
        )
        if response.is_error or response.is_redirect:
            raise EdgeConnectClientError(
                f"POST /gms/rest/authentication/login: HTTP {response.status_code}. "
                "Revisa usuario, contraseña, OTP y permisos de API.",
                status_code=response.status_code,
                method="POST",
                path="/gms/rest/authentication/login",
            )
        if not response.cookies.get("orchCsrfToken"):
            raise EdgeConnectClientError(
                "El login no entregó una sesión con CSRF. Revisa MFA o si el acceso requiere SSO.",
                method="POST",
                path="/gms/rest/authentication/login",
            )
        self._csrf(client, headers)

    @staticmethod
    def _csrf(client: httpx.Client, headers: dict[str, str]) -> None:
        csrf_token = client.cookies.get("orchCsrfToken")
        if csrf_token:
            headers["X-XSRF-TOKEN"] = csrf_token

    def request_otp(self, client: httpx.Client) -> None:
        path = "/gms/rest/authentication/loginToken"
        response = client.post(
            self._url(path),
            json={
                "user": self.orchestrator.username,
                "password": decrypt_secret(self.orchestrator.encrypted_password),
                "TempCode": False,
            },
        )
        if response.status_code not in {200, 204} or "text/html" in response.headers.get(
            "content-type", ""
        ):
            raise EdgeConnectClientError(
                f"POST {path}: HTTP {response.status_code}. "
                "No se pudo iniciar MFA. Revisa URL, credenciales y el método de acceso del Orchestrator.",
                status_code=response.status_code,
                method="POST",
                path=path,
            )

    def _logout(self, client: httpx.Client, headers: dict[str, str]) -> None:
        try:
            client.get(
                self._url("/gms/rest/authentication/logout?source=dashboardapi_ec"),
                headers=headers,
            )
        except httpx.HTTPError:
            # Session expiry is bounded server-side; logout must not hide the API response.
            pass

    @staticmethod
    def _payload(response: httpx.Response) -> dict[str, Any]:
        content_type = response.headers.get("content-type", "")
        if "json" in content_type:
            data = response.json()
            return data if isinstance(data, dict) else {"items": data}
        text = response.text.strip()
        return {"raw": text[:20000]}
