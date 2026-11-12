"""HPE Aruba Networking Central client (new REST API families).

Thin HTTP client for the new Central REST APIs (network-monitoring v1,
network-notifications v1 and network-troubleshooting v1). Authentication uses
HPE GreenLake OAuth2 client credentials: the client fetches an access token
from the SSO token endpoint, caches it with its expiry and transparently
refreshes it (proactively on expiry and reactively on a 401 response).
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

logger = logging.getLogger("ec_mcp.central")

DEFAULT_BASE_URL = "https://us.api.central.arubanetworks.com"
DEFAULT_TOKEN_URL = "https://sso.common.cloud.hpe.com/as/token.oauth2"  # nosec B105
DEFAULT_TIMEOUT = 30.0
TOKEN_EXPIRY_MARGIN = 60.0

MONITORING = "network-monitoring/v1"
NOTIFICATIONS = "network-notifications/v1"
TROUBLESHOOTING = "network-troubleshooting/v1"

DEVICE_FAMILIES = ("aps", "switches", "gateways")
TROUBLESHOOTING_DEVICE_TYPES = ("aps", "gateways", "cx", "aos-s")
ASYNC_OPERATIONS = (
    "showCommands",
    "ping",
    "traceroute",
    "nslookup",
    "tcp",
    "http",
    "https",
    "portBounce",
    "poeBounce",
)


class ArubaCentralError(RuntimeError):
    """Raised when the Central API returns an error."""


class ArubaCentralClient:
    """Minimal client for the new HPE Aruba Networking Central REST APIs."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        base_url: str = DEFAULT_BASE_URL,
        token_url: str = DEFAULT_TOKEN_URL,
        timeout: float = DEFAULT_TIMEOUT,
        verify_tls: bool = True,
        client: httpx.Client | None = None,
    ) -> None:
        if not client_id or not client_secret:
            raise ValueError(
                "Central OAuth2 credentials are required (EC_CENTRAL_CLIENT_ID / EC_CENTRAL_CLIENT_SECRET)"
            )
        self._client_id = client_id.strip()
        self._client_secret = client_secret.strip()
        self._base_url = base_url.rstrip("/")
        self._token_url = token_url
        self._timeout = timeout
        self._verify_tls = verify_tls
        self._client = client or httpx.Client(
            base_url=self._base_url,
            verify=verify_tls,
            timeout=timeout,
        )
        self._access_token = ""  # nosec B105
        self._refresh_token = ""  # nosec B105
        self._expires_at = 0.0

    # --- Token handling -------------------------------------------------

    def _fetch_token(self, grant_type: str) -> None:
        data = {
            "grant_type": grant_type,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }
        if grant_type == "refresh_token":
            if not self._refresh_token:
                raise ArubaCentralError("No refresh token available for Central OAuth2 flow")
            data["refresh_token"] = self._refresh_token
        try:
            response = httpx.post(
                self._token_url,
                data=data,
                timeout=self._timeout,
                verify=self._verify_tls,
            )
        except httpx.HTTPError as error:
            raise ArubaCentralError(f"Central token request failed: {error}") from error
        if response.status_code != 200:
            raise ArubaCentralError(f"Central token request failed: HTTP {response.status_code} {response.text[:300]}")
        payload = response.json()
        self._access_token = payload.get("access_token", "")
        self._refresh_token = payload.get("refresh_token", self._refresh_token)
        expires_in = float(payload.get("expires_in", 3600))
        self._expires_at = time.time() + max(0.0, expires_in - TOKEN_EXPIRY_MARGIN)
        if not self._access_token:
            raise ArubaCentralError("Central token response did not include an access_token")

    def _ensure_token(self) -> None:
        if self._access_token and time.time() < self._expires_at:
            return
        grant = "refresh_token" if self._refresh_token else "client_credentials"
        self._fetch_token(grant)

    # --- Core request ---------------------------------------------------

    def request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        self._ensure_token()
        response = self._send(method, path, params, json_body)
        if response.status_code == 401:
            self._fetch_token("refresh_token" if self._refresh_token else "client_credentials")
            response = self._send(method, path, params, json_body)
        if response.status_code >= 400:
            raise ArubaCentralError(
                f"Central API {method} {path} failed: HTTP {response.status_code} {response.text[:500]}"
            )
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError as error:
            raise ArubaCentralError(
                f"Central API {method} {path} returned a non-JSON response: {response.text[:300]}"
            ) from error

    def _send(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None,
        json_body: dict[str, Any] | None,
    ) -> httpx.Response:
        try:
            return self._client.request(
                method,
                path,
                params={k: v for k, v in (params or {}).items() if v not in (None, "")},
                json=json_body,
                headers={"Authorization": f"Bearer {self._access_token}"},
            )
        except httpx.HTTPError as error:
            raise ArubaCentralError(f"Central API request failed: {error}") from error

    # --- Monitoring -----------------------------------------------------

    def sites_health(self, params: dict[str, Any] | None = None) -> Any:
        return self.request("GET", f"{MONITORING}/sites-health", params=params)

    def sites_device_health(self, params: dict[str, Any] | None = None) -> Any:
        return self.request("GET", f"{MONITORING}/sites-device-health", params=params)

    def sites_client_health(self, params: dict[str, Any] | None = None) -> Any:
        return self.request("GET", f"{MONITORING}/sites-client-health", params=params)

    def list_devices(self, family: str, params: dict[str, Any] | None = None) -> Any:
        if family not in DEVICE_FAMILIES:
            raise ValueError(f"Unsupported device family '{family}'. Use one of {DEVICE_FAMILIES}")
        return self.request("GET", f"{MONITORING}/{family}", params=params)

    def get_device(self, family: str, serial: str) -> Any:
        if family not in DEVICE_FAMILIES:
            raise ValueError(f"Unsupported device family '{family}'. Use one of {DEVICE_FAMILIES}")
        return self.request("GET", f"{MONITORING}/{family}/{serial}")

    def get_device_trends(self, family: str, serial: str, metric: str, params: dict[str, Any] | None = None) -> Any:
        if family not in DEVICE_FAMILIES:
            raise ValueError(f"Unsupported device family '{family}'. Use one of {DEVICE_FAMILIES}")
        return self.request("GET", f"{MONITORING}/{family}/{serial}/{metric}", params=params)

    def list_clients(self, params: dict[str, Any] | None = None) -> Any:
        return self.request("GET", f"{MONITORING}/clients", params=params)

    def client_mobility_trail(self, mac_address: str, params: dict[str, Any] | None = None) -> Any:
        return self.request("GET", f"{MONITORING}/clients/{mac_address}/mobility-trail", params=params)

    def list_wlans(self, params: dict[str, Any] | None = None) -> Any:
        return self.request("GET", f"{MONITORING}/wlans", params=params)

    def get_wlan(self, ssid: str, params: dict[str, Any] | None = None) -> Any:
        from urllib.parse import quote

        return self.request("GET", f"{MONITORING}/wlans/{quote(ssid, safe='')}", params=params)

    def clients_usage(self, params: dict[str, Any] | None = None) -> Any:
        return self.request("GET", f"{MONITORING}/clients-usage", params=params)

    def clients_top_usage(self, params: dict[str, Any] | None = None) -> Any:
        return self.request("GET", f"{MONITORING}/clients-topn-usage", params=params)

    def clients_trend(self, params: dict[str, Any] | None = None) -> Any:
        return self.request("GET", f"{MONITORING}/clients-trend", params=params)

    def client_onboarding(self, view: str, params: dict[str, Any] | None = None) -> Any:
        if view not in ("export", "reasons", "count"):
            raise ValueError("view must be one of: export, reasons, count")
        return self.request("GET", f"{MONITORING}/client-onboarding-stage/{view}", params=params)

    def list_clusters(self, params: dict[str, Any] | None = None) -> Any:
        return self.request("GET", f"{MONITORING}/clusters", params=params)

    def get_cluster(self, cluster_id: str, params: dict[str, Any] | None = None) -> Any:
        return self.request("GET", f"{MONITORING}/clusters/{cluster_id}", params=params)

    # --- Notifications / events ------------------------------------------

    def get_alerts(self, params: dict[str, Any] | None = None) -> Any:
        return self.request("GET", f"{NOTIFICATIONS}/alerts", params=params)

    def get_events(self, params: dict[str, Any] | None = None) -> Any:
        return self.request("GET", f"{TROUBLESHOOTING}/events", params=params)

    # --- Troubleshooting --------------------------------------------------

    def list_show_commands(self, device_type: str, serial: str) -> Any:
        return self.request("GET", f"{TROUBLESHOOTING}/{device_type}/{serial}/showCommands")

    def run_show_commands(self, device_type: str, serial: str, commands: list[str]) -> Any:
        return self.request(
            "POST",
            f"{TROUBLESHOOTING}/{device_type}/{serial}/showCommands",
            json_body={"commands": commands},
        )

    def get_task_result(self, device_type: str, serial: str, task_id: str, operation: str = "showCommands") -> Any:
        if operation not in ASYNC_OPERATIONS:
            raise ValueError(f"Unsupported operation '{operation}'. Use one of {sorted(ASYNC_OPERATIONS)}")
        return self.request(
            "GET",
            f"{TROUBLESHOOTING}/{device_type}/{serial}/{operation}/async-operations/{task_id}",
        )

    def run_network_test(
        self,
        device_type: str,
        serial: str,
        endpoint: str,
        body: dict[str, Any],
    ) -> Any:
        return self.request(
            "POST",
            f"{TROUBLESHOOTING}/{device_type}/{serial}/{endpoint}",
            json_body=body,
        )

    def bounce_port(self, device_type: str, serial: str, ports: list[str], mode: str = "port") -> Any:
        endpoint = "portBounce" if mode == "port" else "poeBounce"
        return self.request(
            "POST",
            f"{TROUBLESHOOTING}/{device_type}/{serial}/{endpoint}",
            json_body={"ports": ports},
        )
