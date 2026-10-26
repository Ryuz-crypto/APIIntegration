"""Dashboard data collection and HTML rendering for EdgeConnect + Axis SSE.

collect_dashboard_payload() gathers a compact, redacted snapshot from the
Orchestrator (inventory, reachability, WAN health, tunnels, alarms, HA) and
optionally from Axis Security (platform health, connectors, tunnels). It is
tolerant: every section degrades to an error note instead of failing the
whole snapshot.

render_dashboard_html() produces a single self-contained HTML file (inline
CSS/JS, no external dependencies) that auto-refreshes from an embedded
`data.json`-style payload, so the same file can be served by nginx on a
remote Ubuntu server and stay live.
"""

from __future__ import annotations

import html
import json
import time
from typing import Any

from .axis_client import AxisSecurityClient
from .axis_workflow import (
    summarize_connector_status,
    summarize_health,
    summarize_tunnel_status,
    unwrap_paged,
)
from .orchestrator_client import OrchestratorClient
from .security import redact_sensitive_values

DASHBOARD_TITLE = "ec-mcp NOC Dashboard"
DASHBOARD_VERSION = "1.0.0"


def _safe(label: str, fn, *args, **kwargs) -> Any:
    try:
        return fn(*args, **kwargs)
    except Exception as error:
        return {"error": f"{label}: {error}"[:300]}


def _collect_edgeconnect(client: OrchestratorClient, kpi_get, project_wan_health_stats, reachability_map) -> dict[str, Any]:
    inventory = _safe("list_appliances", client.list_appliances, refresh=True)
    if isinstance(inventory, dict) and "error" in inventory:
        return {"available": False, "error": inventory["error"], "appliances": []}
    appliances = inventory if isinstance(inventory, list) else []

    reach = _safe("reachability", reachability_map, client)
    if not isinstance(reach, dict):
        reach = {}

    rows = []
    for appliance in appliances:
        ne_pk = str(appliance.get("nePk") or "")
        entry: dict[str, Any] = {
            "nePk": ne_pk,
            "name": appliance.get("name"),
            "model": appliance.get("model"),
            "software_version": appliance.get("software_version"),
            "ip": appliance.get("ip"),
            "lan_ip": appliance.get("lan_ip"),
            "wan_ips": appliance.get("wan_ips") or [],
            "state": appliance.get("state"),
            "reachability": reach.get(ne_pk, appliance.get("reachability")),
        }
        if ne_pk:
            entry["tunnel_state"] = _safe(
                "tunnel_state", kpi_get, client, "tunnel_state", ne_pk
            )
            entry["ha_status"] = _safe(
                "ha_status", kpi_get, client, "ha_status", ne_pk
            )
            entry["alarms"] = _safe(
                "alarms", client.get_raw, "/alarm/count/appliance", nePk=ne_pk
            )
        rows.append(entry)

    wan_health = _safe(
        "wan_health",
        lambda: [
            {
                "nePk": str(a.get("nePk") or ""),
                "latency": project_wan_health_stats(
                    kpi_get(client, "latency", str(a.get("nePk") or ""), "hour")
                ),
                "mos": project_wan_health_stats(
                    kpi_get(client, "mos", str(a.get("nePk") or ""), "hour")
                ),
            }
            for a in appliances
            if a.get("nePk")
        ],
    )

    return {
        "available": True,
        "collected_at": time.time(),
        "appliances": rows,
        "wan_health": wan_health,
        "counts": {
            "appliances": len(rows),
            "reachable": sum(
                1
                for r in rows
                if str(r.get("reachability") or "").lower() in ("ok", "reachable", "up", "")
            ),
        },
    }


def _collect_axis(axis: AxisSecurityClient | None) -> dict[str, Any]:
    if axis is None:
        return {"available": False, "reason": "Axis Security is not enabled (EC_AXIS_ENABLED)"}
    try:
        raw_health = axis.health()
    except Exception as error:
        return {
            "available": False,
            "reason": "Axis Security is enabled but unreachable",
            "error": str(error)[:300],
        }
    health = _safe("health", summarize_health, raw_health)
    connectors_raw = _safe("list_connectors", axis.list_connectors, page_size=100)
    connectors = []
    if isinstance(connectors_raw, dict) and "error" not in connectors_raw:
        for connector in unwrap_paged(connectors_raw):
            cid = str(connector.get("id") or "")
            entry = {"id": cid, "name": connector.get("name"), "enabled": connector.get("enabled")}
            if cid:
                entry["status"] = _safe(
                    "connector_status", summarize_connector_status, axis.connector_status(cid)
                )
            connectors.append(entry)
    elif isinstance(connectors_raw, dict):
        connectors = [{"error": connectors_raw["error"]}]
    tunnels_raw = _safe("list_tunnels", axis.list_tunnels, page_size=100)
    tunnels = []
    if isinstance(tunnels_raw, dict) and "error" not in tunnels_raw:
        for tunnel in unwrap_paged(tunnels_raw):
            tid = str(tunnel.get("id") or "")
            entry = {"id": tid, "name": tunnel.get("name")}
            if tid:
                entry["status"] = _safe(
                    "tunnel_status", summarize_tunnel_status, axis.tunnel_status(tid)
                )
            tunnels.append(entry)
    elif isinstance(tunnels_raw, dict):
        tunnels = [{"error": tunnels_raw["error"]}]
    return {
        "available": True,
        "collected_at": time.time(),
        "health": health,
        "connectors": connectors,
        "tunnels": tunnels,
        "counts": {"connectors": len(connectors), "tunnels": len(tunnels)},
    }


def collect_dashboard_payload(
    client: OrchestratorClient | None,
    axis: AxisSecurityClient | None,
    *,
    kpi_get=None,
    project_wan_health_stats=None,
    reachability_map=None,
) -> dict[str, Any]:
    """Collect a full dashboard snapshot. `client`/`axis` may be None."""
    payload: dict[str, Any] = {
        "generated_at": time.time(),
        "title": DASHBOARD_TITLE,
        "edgeconnect": {"available": False, "reason": "Orchestrator is not configured"},
        "axis": {"available": False, "reason": "Axis Security is not enabled"},
    }
    if client is not None:
        if kpi_get is None or project_wan_health_stats is None or reachability_map is None:
            raise ValueError(
                "EdgeConnect dashboard helpers must be supplied by the server instance."
            )
        payload["edgeconnect"] = _collect_edgeconnect(
            client, kpi_get, project_wan_health_stats, reachability_map
        )
    if axis is not None:
        payload["axis"] = _collect_axis(axis)
    payload = redact_sensitive_values(payload)
    return payload


def _kpi_cards(payload: dict[str, Any]) -> str:
    ec = payload.get("edgeconnect") or {}
    ax = payload.get("axis") or {}
    ec_counts = ec.get("counts") or {}
    ec_available = ec.get("available")
    ax_health = (ax.get("health") or {}).get("status") if ax.get("available") else None
    cards = [
        ("Appliances", str(ec_counts.get("appliances", 0)), "ok" if ec_available else "bad"),
        ("Reachability", str(ec_counts.get("reachable", 0)), "ok" if ec_available else "bad"),
        ("Axis Health", str(ax_health or "—"), "ok" if ax_health == "Healthy" else ("bad" if ax_health else "warn")),
        ("Axis Connectors", str((ax.get("counts") or {}).get("connectors", 0)), "ok" if ax.get("available") else "warn"),
        ("Axis Tunnels", str((ax.get("counts") or {}).get("tunnels", 0)), "ok" if ax.get("available") else "warn"),
    ]
    return '<div class="cards">' + "".join(
        f'<div class="card {cls}"><span class="card-label">{html.escape(label)}</span>'
        f'<span class="card-value">{html.escape(value)}</span></div>'
        for label, value, cls in cards
    ) + "</div>"


def render_dashboard_html(payload: dict[str, Any], *, refresh_seconds: int = 30) -> str:
    """Render a self-contained interactive HTML dashboard from a payload."""
    embedded = json.dumps(payload, ensure_ascii=False, default=str).replace("</", "<\\/")
    ec = payload.get("edgeconnect") or {}
    ax = payload.get("axis") or {}
    ec_rows = ""
    if ec.get("available"):
        for a in ec.get("appliances") or []:
            reach = str(a.get("reachability") or "—")
            reach_cls = "ok" if reach.lower() in ("ok", "reachable", "up", "") else "bad"
            ec_rows += (
                "<tr>"
                f"<td>{html.escape(str(a.get('name') or ''))}</td>"
                f"<td>{html.escape(str(a.get('nePk') or ''))}</td>"
                f"<td>{html.escape(str(a.get('model') or ''))}</td>"
                f"<td>{html.escape(str(a.get('software_version') or ''))}</td>"
                f"<td>{html.escape(str(a.get('ip') or ''))}</td>"
                f'<td class="{reach_cls}">{html.escape(reach)}</td>'
                "</tr>"
            )
        if not ec_rows:
            ec_rows = '<tr><td colspan="6" class="muted">Sin appliances en inventario</td></tr>'
    else:
        ec_rows = f'<tr><td colspan="6" class="muted">EdgeConnect no disponible: {html.escape(str(ec.get("error") or ec.get("reason") or ""))}</td></tr>'

    ax_rows = ""
    if ax.get("available"):
        for c in ax.get("connectors") or []:
            status = "—"
            cls = "warn"
            if isinstance(c.get("status"), dict):
                status = str(c["status"].get("status") or "—")
                cls = "ok" if status == "Available" else "bad"
            ax_rows += (
                "<tr>"
                f"<td>{html.escape(str(c.get('name') or ''))}</td>"
                f"<td>{html.escape(str(c.get('id') or ''))}</td>"
                f'<td class="{cls}">{html.escape(status)}</td>'
                "</tr>"
            )
        for t in ax.get("tunnels") or []:
            status = "—"
            cls = "warn"
            if isinstance(t.get("status"), dict):
                status = str(t["status"].get("status") or "—")
                cls = "ok" if status == "Online" else "bad"
            ax_rows += (
                "<tr>"
                f"<td>{html.escape(str(t.get('name') or ''))}</td>"
                f"<td>{html.escape(str(t.get('id') or ''))}</td>"
                f'<td class="{cls}">{html.escape(status)}</td>'
                "</tr>"
            )
        if not ax_rows:
            ax_rows = '<tr><td colspan="3" class="muted">Sin connectors ni túneles</td></tr>'
    else:
        ax_rows = f'<tr><td colspan="3" class="muted">Axis no disponible: {html.escape(str(ax.get("reason") or ""))}</td></tr>'

    generated = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(payload.get("generated_at") or time.time()))
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>{html.escape(DASHBOARD_TITLE)}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="{refresh_seconds}">
<style>
:root{{color-scheme:dark;--bg:#07111f;--panel:#101d30;--line:#2c3d55;--text:#e7eef8;--muted:#94a8c2;--ok:#22c55e;--warn:#f59e0b;--bad:#ef4444}}
*{{box-sizing:border-box}}body{{font-family:Inter,ui-sans-serif,system-ui,sans-serif;background:var(--bg);color:var(--text);margin:0;padding:24px}}
h1{{font-size:1.4rem;margin:0 0 4px}}h2{{font-size:1.05rem;color:#bae6fd;margin:26px 0 10px}}
.muted{{color:var(--muted)}}header{{display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:8px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-top:18px}}
.card{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px;display:flex;flex-direction:column;gap:6px}}
.card-label{{font-size:.78rem;color:var(--muted)}}.card-value{{font-size:1.6rem;font-weight:800}}
.card.ok{{border-color:#166534}}.card.warn{{border-color:#92610a}}.card.bad{{border-color:#991b1b}}
table{{width:100%;border-collapse:collapse;margin-top:8px;font-size:.86rem}}
th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line)}}
th{{color:var(--muted);font-size:.75rem;text-transform:uppercase}}
td.ok{{color:var(--ok);font-weight:700}}td.bad{{color:var(--bad);font-weight:700}}td.warn{{color:var(--warn);font-weight:700}}
.panel{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px;margin-top:16px}}
</style></head><body>
<header><h1>{html.escape(DASHBOARD_TITLE)}</h1><span class="muted">v{DASHBOARD_VERSION} · generado {html.escape(generated)} · auto-refresh {refresh_seconds}s</span></header>
{_kpi_cards(payload)}
<section class="panel"><h2>EdgeConnect — Appliances</h2>
<table><thead><tr><th>Nombre</th><th>nePk</th><th>Modelo</th><th>Software</th><th>IP mgmt</th><th>Reachability</th></tr></thead>
<tbody>{ec_rows}</tbody></table></section>
<section class="panel"><h2>Axis Security (SSE) — Connectors y Túneles</h2>
<table><thead><tr><th>Nombre</th><th>ID</th><th>Estado</th></tr></thead>
<tbody>{ax_rows}</tbody></table></section>
<details class="panel"><summary class="muted">Datos crudos (JSON embebido)</summary><pre id="raw" style="max-height:420px;overflow:auto;font-size:.72rem"></pre></details>
<script>document.getElementById('raw').textContent=JSON.stringify({embedded},null,2);</script>
</body></html>"""
