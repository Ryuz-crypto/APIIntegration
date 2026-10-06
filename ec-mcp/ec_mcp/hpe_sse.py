"""Bounded, read-only adapter for documented pyhpesse AdminApi GET resources.

The SDK's API contract is useful, but its request helper does not reliably raise on
HTTP failures and disables TLS warnings process-wide. Keep transport policy local.
"""

from __future__ import annotations

from urllib.parse import urlsplit

import httpx

from .config import Settings

SSE_RESOURCES = {
    "web_categories": "/api/v1.0/WebCategories",
    "custom_ip_categories": "/api/v1.0/IpCategories",
    "ip_feed_categories": "/api/v1.0/IpCategoriesFeed",
    "ssl_exclusions": "/api/v1.0/SslExclusions",
    "locations": "/api/v1.0/Locations",
    "tunnels": "/api/v1.0/Tunnels",
    "health": "/api/v1.0/Health",
}


class SSEAdminClient:
    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        if not settings.hpe_sse_api_token.strip():
            raise ValueError("EC_HPE_SSE_API_TOKEN is not configured")
        url = urlsplit(settings.hpe_sse_api_url)
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.path not in {"", "/"} or url.query or url.fragment:
            raise ValueError("EC_HPE_SSE_API_URL must be an HTTPS origin without path, credentials or query")
        self._token = settings.hpe_sse_api_token.strip()
        self._client = client or httpx.Client(base_url=settings.hpe_sse_api_url, verify=True, timeout=15.0, follow_redirects=False)
        self._owns_client = client is None

    def __enter__(self) -> SSEAdminClient:
        return self

    def __exit__(self, *args: object) -> None:
        if self._owns_client:
            self._client.close()

    def read(self, resource: str, page: int = 1, page_size: int = 50) -> dict:
        if resource not in SSE_RESOURCES:
            raise ValueError(f"Unknown SSE resource; valid: {sorted(SSE_RESOURCES)}")
        if type(page) is not int or not 1 <= page <= 10_000:
            raise ValueError("page must be between 1 and 10000")
        if type(page_size) is not int or not 1 <= page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")
        params = {} if resource == "health" else {"pagenumber": page, "pagesize": page_size}
        try:
            response = self._client.get(
                SSE_RESOURCES[resource],
                params=params,
                headers={"Authorization": f"Bearer {self._token}", "Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as error:
            raise RuntimeError(f"HPE SSE returned HTTP {error.response.status_code} for {resource}") from None
        except (httpx.HTTPError, ValueError) as error:
            raise RuntimeError(f"HPE SSE request failed for {resource}: {type(error).__name__}") from None
        if not isinstance(payload, dict):
            raise RuntimeError(f"HPE SSE returned an unexpected response for {resource}")
        if payload.get("success") is False or payload.get("error") or payload.get("errors") or str(payload.get("status", "")).lower() in {"error", "failed"}:
            raise RuntimeError(f"HPE SSE reported an API error for {resource}")
        return {
            "resource": resource,
            "page": None if resource == "health" else page,
            "page_size": None if resource == "health" else page_size,
            "response": payload,
            "evidence_scope": "sse_admin_inventory_only",
            "policy_decision_observed": False,
            "enforcement_verified": False,
        }
