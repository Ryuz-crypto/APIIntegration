"""Axis Security PublicAdminApi client.

Thin HTTP client for the Axis Security SSE admin API
(https://admin-api.axissecurity.com/api/v1.0). Authentication is a single
Bearer JWT token (EC_AXIS_ADMIN_TOKEN). All requests are JSON over HTTPS.

The client is intentionally small: it exposes typed helpers per resource
(Tags, Applications, Connectors, ConnectorZones, IpCategories, ...,
Locations, SubLocations, Tunnels, Users, WebCategories, Health, Commit)
and a generic `request` method for anything not covered.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger("ec_mcp.axis")

DEFAULT_BASE_URL = "https://admin-api.axissecurity.com"
API_PREFIX = "/api/v1.0"
DEFAULT_TIMEOUT = 30.0


class AxisSecurityError(RuntimeError):
    """Raised when the Axis admin API returns an error."""


class AxisSecurityClient:
    """Minimal client for the Axis Security PublicAdminApi v1.0."""

    def __init__(
        self,
        token: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        verify_tls: bool = True,
        client: httpx.Client | None = None,
    ):
        if not token:
            raise ValueError("Axis admin token is required (EC_AXIS_ADMIN_TOKEN)")
        self._token = token.strip()
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._verify_tls = verify_tls
        self._client = client or httpx.Client(
            base_url=self._base_url,
            verify=verify_tls,
            timeout=timeout,
        )
        self._client.headers.update(self._headers())
        self._headers_cache = self._headers()
        self._metrics: dict[str, dict[str, float]] = {}

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def close(self) -> None:
        self._client.close()

    def metrics(self) -> dict[str, dict[str, float]]:
        return self._metrics

    def _record(self, label: str, elapsed: float, size: int) -> None:
        entry = self._metrics.setdefault(
            label, {"calls": 0.0, "total_time": 0.0, "max_time": 0.0, "total_bytes": 0.0}
        )
        entry["calls"] += 1
        entry["total_time"] += elapsed
        entry["max_time"] = max(entry["max_time"], elapsed)
        entry["total_bytes"] += size

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        """Perform an API request. `path` is relative to /api/v1.0."""
        if not path.startswith("/"):
            path = "/" + path
        full_path = f"{API_PREFIX}{path}"
        label = f"{method} {path}"
        started = time.monotonic()
        response = self._client.request(
            method,
            full_path,
            headers=self._headers(),
            params={k: v for k, v in (params or {}).items() if v is not None},
            json=json_body,
        )
        elapsed = time.monotonic() - started
        self._record(label, elapsed, len(response.content))
        if response.status_code >= 400:
            raise AxisSecurityError(self._error_message(response, f"{method} {full_path}"))
        if not response.content:
            return None
        try:
            return response.json()
        except json.JSONDecodeError as error:
            raise AxisSecurityError(
                f"Axis API returned non-JSON response for {method} {path}"
            ) from error

    def _error_message(self, response: httpx.Response, action: str) -> str:
        detail = ""
        try:
            body = response.json()
            detail = str(body.get("details") or body.get("message") or body.get("error") or body)[:300]
        except Exception:
            detail = response.text[:300]
        hints = {
            400: "Bad request: check the body/query parameters.",
            401: "Unauthorized: the Axis admin token is missing or expired.",
            403: "Forbidden: the token lacks permission for this resource.",
            404: "Not found: the entity id does not exist.",
            409: "Conflict: an entity with the same name/id already exists.",
            500: "Internal server error on the Axis side.",
        }
        hint = hints.get(response.status_code, "")
        return f"Axis API HTTP {response.status_code} for {action}: {detail!r}. {hint}".strip()

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------
    def health(self) -> dict[str, Any]:
        return self.request("GET", "/Health")

    # ------------------------------------------------------------------
    # Tags (Application Groups)
    # ------------------------------------------------------------------
    def list_tags(self, page_number: int = 1, page_size: int = 50) -> dict[str, Any]:
        return self.request("GET", "/Tags", params={"pageNumber": page_number, "pageSize": page_size})

    def get_tag(self, tag_id: str) -> dict[str, Any]:
        return self.request("GET", f"/Tags/{tag_id}")

    def create_tag(self, body: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/Tags", json_body=body)

    def update_tag(self, tag_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return self.request("PUT", f"/Tags/{tag_id}", json_body=body)

    def delete_tag(self, tag_id: str) -> None:
        self.request("DELETE", f"/Tags/{tag_id}")

    # ------------------------------------------------------------------
    # Applications
    # ------------------------------------------------------------------
    def list_applications(self, page_number: int = 1, page_size: int = 50) -> dict[str, Any]:
        return self.request("GET", "/Applications", params={"pageNumber": page_number, "pageSize": page_size})

    def get_application(self, app_id: str) -> dict[str, Any]:
        return self.request("GET", f"/Applications/{app_id}")

    def create_application(self, body: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/Applications", json_body=body)

    def update_application(self, app_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return self.request("PUT", f"/Applications/{app_id}", json_body=body)

    def delete_application(self, app_id: str) -> None:
        self.request("DELETE", f"/Applications/{app_id}")

    # ------------------------------------------------------------------
    # Connectors
    # ------------------------------------------------------------------
    def list_connectors(self, page_number: int = 1, page_size: int = 50) -> dict[str, Any]:
        return self.request("GET", "/Connectors", params={"pageNumber": page_number, "pageSize": page_size})

    def get_connector(self, connector_id: str) -> dict[str, Any]:
        return self.request("GET", f"/Connectors/{connector_id}")

    def create_connector(self, body: dict[str, Any]) -> dict[str, Any]:
        """Create a connector. Returns ConnectorCreateResponseModelV1 (includes install command)."""
        return self.request("POST", "/Connectors", json_body=body)

    def update_connector(self, connector_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return self.request("PUT", f"/Connectors/{connector_id}", json_body=body)

    def delete_connector(self, connector_id: str) -> None:
        self.request("DELETE", f"/Connectors/{connector_id}")

    def regenerate_connector(self, connector_id: str) -> dict[str, Any]:
        """Regenerate the installation command for an existing connector."""
        return self.request("POST", f"/Connectors/{connector_id}/regenerate")

    def connector_status(self, connector_id: str) -> dict[str, Any]:
        """Get live status: network/memory/disk/CPU/machine health."""
        return self.request("GET", f"/Connectors/{connector_id}/status")

    # ------------------------------------------------------------------
    # Connector Zones
    # ------------------------------------------------------------------
    def list_connector_zones(self, page_number: int = 1, page_size: int = 50) -> dict[str, Any]:
        return self.request("GET", "/ConnectorZones", params={"pageNumber": page_number, "pageSize": page_size})

    def get_connector_zone(self, zone_id: str) -> dict[str, Any]:
        return self.request("GET", f"/ConnectorZones/{zone_id}")

    def create_connector_zone(self, body: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/ConnectorZones", json_body=body)

    def update_connector_zone(self, zone_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return self.request("PUT", f"/ConnectorZones/{zone_id}", json_body=body)

    def delete_connector_zone(self, zone_id: str) -> None:
        self.request("DELETE", f"/ConnectorZones/{zone_id}")

    # ------------------------------------------------------------------
    # Custom IP Categories
    # ------------------------------------------------------------------
    def list_ip_categories(self, page_number: int = 1, page_size: int = 50) -> dict[str, Any]:
        return self.request("GET", "/IpCategories", params={"pageNumber": page_number, "pageSize": page_size})

    def get_ip_category(self, category_id: str) -> dict[str, Any]:
        return self.request("GET", f"/IpCategories/{category_id}")

    def create_ip_category(self, body: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/IpCategories", json_body=body)

    def update_ip_category(self, category_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return self.request("PUT", f"/IpCategories/{category_id}", json_body=body)

    def delete_ip_category(self, category_id: str) -> None:
        self.request("DELETE", f"/IpCategories/{category_id}")

    # ------------------------------------------------------------------
    # IP Feed Categories
    # ------------------------------------------------------------------
    def list_ip_feed_categories(self, page_number: int = 1, page_size: int = 50) -> dict[str, Any]:
        return self.request("GET", "/IpCategoriesFeed", params={"pageNumber": page_number, "pageSize": page_size})

    def get_ip_feed_category(self, category_id: str) -> dict[str, Any]:
        return self.request("GET", f"/IpCategoriesFeed/{category_id}")

    def create_ip_feed_category(self, body: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/IpCategoriesFeed", json_body=body)

    def update_ip_feed_category(self, category_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return self.request("PUT", f"/IpCategoriesFeed/{category_id}", json_body=body)

    def delete_ip_feed_category(self, category_id: str) -> None:
        self.request("DELETE", f"/IpCategoriesFeed/{category_id}")

    # ------------------------------------------------------------------
    # Web Categories
    # ------------------------------------------------------------------
    def list_web_categories(self, page_number: int = 1, page_size: int = 50) -> dict[str, Any]:
        return self.request("GET", "/WebCategories", params={"pageNumber": page_number, "pageSize": page_size})

    def get_web_category(self, category_id: str) -> dict[str, Any]:
        return self.request("GET", f"/WebCategories/{category_id}")

    def create_web_category(self, body: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/WebCategories", json_body=body)

    def update_web_category(self, category_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return self.request("PUT", f"/WebCategories/{category_id}", json_body=body)

    def delete_web_category(self, category_id: str) -> None:
        self.request("DELETE", f"/WebCategories/{category_id}")

    # ------------------------------------------------------------------
    # SSL Exclusions
    # ------------------------------------------------------------------
    def list_ssl_exclusions(self, page_number: int = 1, page_size: int = 50) -> dict[str, Any]:
        return self.request("GET", "/SslExclusions", params={"pageNumber": page_number, "pageSize": page_size})

    def get_ssl_exclusion(self, exclusion_id: str) -> dict[str, Any]:
        return self.request("GET", f"/SslExclusions/{exclusion_id}")

    def create_ssl_exclusion(self, body: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/SslExclusions", json_body=body)

    def update_ssl_exclusion(self, exclusion_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return self.request("PUT", f"/SslExclusions/{exclusion_id}", json_body=body)

    def delete_ssl_exclusion(self, exclusion_id: str) -> None:
        self.request("DELETE", f"/SslExclusions/{exclusion_id}")

    # ------------------------------------------------------------------
    # Groups
    # ------------------------------------------------------------------
    def list_groups(self, page_number: int = 1, page_size: int = 50) -> dict[str, Any]:
        return self.request("GET", "/Groups", params={"pageNumber": page_number, "pageSize": page_size})

    def get_group(self, group_id: str) -> dict[str, Any]:
        return self.request("GET", f"/Groups/{group_id}")

    def create_group(self, body: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/Groups", json_body=body)

    def update_group(self, group_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return self.request("PUT", f"/Groups/{group_id}", json_body=body)

    def delete_group(self, group_id: str) -> None:
        self.request("DELETE", f"/Groups/{group_id}")

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------
    def list_users(self, page_number: int = 1, page_size: int = 50) -> dict[str, Any]:
        return self.request("GET", "/Users", params={"pageNumber": page_number, "pageSize": page_size})

    def get_user(self, user_id: str) -> dict[str, Any]:
        return self.request("GET", f"/Users/{user_id}")

    def create_user(self, body: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/Users", json_body=body)

    def update_user(self, user_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return self.request("PUT", f"/Users/{user_id}", json_body=body)

    def delete_user(self, user_id: str) -> None:
        self.request("DELETE", f"/Users/{user_id}")

    # ------------------------------------------------------------------
    # Locations
    # ------------------------------------------------------------------
    def list_locations(self, page_number: int = 1, page_size: int = 50) -> dict[str, Any]:
        return self.request("GET", "/Locations", params={"pageNumber": page_number, "pageSize": page_size})

    def get_location(self, location_id: str) -> dict[str, Any]:
        return self.request("GET", f"/Locations/{location_id}")

    def create_location(self, body: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/Locations", json_body=body)

    def update_location(self, location_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return self.request("PUT", f"/Locations/{location_id}", json_body=body)

    def delete_location(self, location_id: str) -> None:
        self.request("DELETE", f"/Locations/{location_id}")

    # ------------------------------------------------------------------
    # SubLocations
    # ------------------------------------------------------------------
    def list_sub_locations(self, location_id: str, page_number: int = 1, page_size: int = 50) -> dict[str, Any]:
        return self.request(
            "GET",
            f"/Locations/{location_id}/SubLocations",
            params={"pageNumber": page_number, "pageSize": page_size},
        )

    def get_sub_location(self, location_id: str, sub_location_id: str) -> dict[str, Any]:
        return self.request("GET", f"/Locations/{location_id}/SubLocations/{sub_location_id}")

    def create_sub_location(self, location_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", f"/Locations/{location_id}/SubLocations", json_body=body)

    def update_sub_location(self, location_id: str, sub_location_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return self.request("PUT", f"/Locations/{location_id}/SubLocations/{sub_location_id}", json_body=body)

    def delete_sub_location(self, location_id: str, sub_location_id: str) -> None:
        self.request("DELETE", f"/Locations/{location_id}/SubLocations/{sub_location_id}")

    # ------------------------------------------------------------------
    # Tunnels
    # ------------------------------------------------------------------
    def list_tunnels(self, page_number: int = 1, page_size: int = 50) -> dict[str, Any]:
        return self.request("GET", "/Tunnels", params={"pageNumber": page_number, "pageSize": page_size})

    def get_tunnel(self, tunnel_id: str) -> dict[str, Any]:
        return self.request("GET", f"/Tunnels/{tunnel_id}")

    def create_tunnel(self, body: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/Tunnels", json_body=body)

    def update_tunnel(self, tunnel_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return self.request("PUT", f"/Tunnels/{tunnel_id}", json_body=body)

    def delete_tunnel(self, tunnel_id: str) -> None:
        self.request("DELETE", f"/Tunnels/{tunnel_id}")

    def tunnel_status(self, tunnel_id: str) -> dict[str, Any]:
        return self.request("GET", f"/Tunnels/{tunnel_id}/status")

    # ------------------------------------------------------------------
    # Domain Name Certificates
    # ------------------------------------------------------------------
    def list_certificates(self, page_number: int = 1, page_size: int = 50) -> dict[str, Any]:
        return self.request("GET", "/DomainNameCertificates", params={"pageNumber": page_number, "pageSize": page_size})

    def get_certificate(self, cert_id: str) -> dict[str, Any]:
        return self.request("GET", f"/DomainNameCertificates/{cert_id}")

    def create_certificate(self, body: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/DomainNameCertificates", json_body=body)

    def delete_certificate(self, cert_id: str) -> None:
        self.request("DELETE", f"/DomainNameCertificates/{cert_id}")

    def replace_certificate(self, cert_id: str, body: dict[str, Any]) -> dict[str, Any]:
        """Replace a certificate (PFX). Body: {certificateBase64, certificatePassword}."""
        return self.request("POST", f"/DomainNameCertificates/{cert_id}/replace", json_body=body)

    # ------------------------------------------------------------------
    # IPSec PoP Locations
    # ------------------------------------------------------------------
    def list_ipsec_locations(self) -> dict[str, Any]:
        """Get available IPSec PoP locations (countries, cities, FQDNs, IPs)."""
        return self.request("GET", "/pops/ipsec")

    # ------------------------------------------------------------------
    # Commit
    # ------------------------------------------------------------------
    def commit_changes(self) -> None:
        """Commit all pending changes. Returns 204 on success."""
        self.request("POST", "/Commit")
