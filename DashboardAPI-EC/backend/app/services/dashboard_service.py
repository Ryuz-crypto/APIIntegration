from collections import Counter
from datetime import UTC, datetime
from statistics import mean

from sqlalchemy import desc
from sqlmodel import Session, select

from app.models.api_sample import ApiSample
from app.models.appliance import Appliance
from app.models.network_resource import MetricPoint, NetworkResource
from app.models.orchestrator import Orchestrator
from app.schemas.dashboard import DashboardRead, DashboardSection, DashboardWidget, WidgetProvenance


def compose_dashboard(session: Session, orchestrator: Orchestrator) -> DashboardRead:
    appliances = list(
        session.exec(select(Appliance).where(Appliance.orchestrator_id == orchestrator.id)).all()
    )
    resources = list(
        session.exec(
            select(NetworkResource).where(NetworkResource.orchestrator_id == orchestrator.id)
        ).all()
    )
    samples = list(
        session.exec(
            select(ApiSample)
            .where(ApiSample.orchestrator_id == orchestrator.id)
            .order_by(desc(ApiSample.created_at))
            .limit(200)
        ).all()
    )
    metrics = list(
        session.exec(
            select(MetricPoint)
            .where(MetricPoint.orchestrator_id == orchestrator.id)
            .order_by(desc(MetricPoint.observed_at))
            .limit(100)
        ).all()
    )
    operations = {
        key
        for key, available in orchestrator.capabilities.get("operations", {}).items()
        if available
    }
    latest = {}
    for sample in samples:
        latest.setdefault(sample.operation_id, sample)

    inventory = "orchestrator.inventory.summary"
    performance = "appliance.performance"
    sites = [resource for resource in resources if resource.resource_type == "site"]
    version_counts = Counter(item.software_version or "Sin versión" for item in appliances)
    successful = sum(1 for item in samples if item.ok)
    api_health = round(successful * 100 / len(samples), 1) if samples else 0
    durations = [item.duration_ms for item in samples if item.duration_ms is not None]
    interface_rows = _all_sample_rows(samples, "appliance.interfaces", "interfaces")
    tunnel_rows = _all_sample_rows(samples, "appliance.tunnels", "tunnels")
    interface_issues = _state_issues(interface_rows)
    tunnel_issues = _state_issues(tunnel_rows)
    anomalies = _metric_anomalies(metrics)
    stale_minutes = _age_minutes(samples[0].created_at) if samples else None
    fleet_health = (
        max(
            0,
            round(
                api_health
                - min(35, len(anomalies) * 4)
                - min(20, interface_issues * 3)
                - min(20, tunnel_issues * 4),
                1,
            ),
        )
        if samples
        else 0
    )
    risk_rows = _risk_by_site(appliances, anomalies, interface_rows, tunnel_rows)
    metric_data = [
        {
            "name": point.metric_name,
            "value": point.value,
            "unit": point.unit,
            "hostname": point.dimensions.get("hostname"),
            "observed_at": point.observed_at.isoformat(),
        }
        for point in metrics[:24]
    ]

    sections = [
        DashboardSection(
            id="realtime",
            title="Pulso en tiempo real",
            widgets=[
                _widget(
                    operations,
                    latest,
                    widget_id="fleet-health",
                    title="Salud correlacionada",
                    description="Índice calculado con disponibilidad API, métricas, interfaces y túneles.",
                    visualization="stat",
                    required=[],
                    value=fleet_health,
                    unit="%",
                    data=[
                        {
                            "api_success": api_health,
                            "metric_alerts": len(anomalies),
                            "interface_issues": interface_issues,
                            "tunnel_issues": tunnel_issues,
                        }
                    ],
                ),
                _widget(
                    operations,
                    latest,
                    widget_id="active-signals",
                    title="Señales activas",
                    description="Umbrales operativos detectados en las métricas normalizadas.",
                    visualization="table",
                    required=[performance],
                    value=len(anomalies),
                    unit="alertas",
                    data=anomalies[:12],
                ),
                _widget(
                    operations,
                    latest,
                    widget_id="freshness",
                    title="Frescura de telemetría",
                    description="Tiempo transcurrido desde la última respuesta almacenada.",
                    visualization="stat",
                    required=[],
                    value=stale_minutes if stale_minutes is not None else "—",
                    unit="min",
                    data=[{"last_sample": samples[0].created_at.isoformat()}] if samples else [],
                ),
                _widget(
                    operations,
                    latest,
                    widget_id="api-latency",
                    title="Latencia API",
                    description="Promedio de respuesta y operaciones más lentas del período reciente.",
                    visualization="bars",
                    required=[],
                    value=round(mean(durations), 1) if durations else "—",
                    unit="ms",
                    data=_operation_latency(samples),
                ),
            ],
        ),
        DashboardSection(
            id="fleet",
            title="Inventario detectado",
            widgets=[
                _widget(
                    operations,
                    latest,
                    widget_id="appliances",
                    title="Appliances",
                    description="Equipos administrados detectados por el Orchestrator.",
                    visualization="stat",
                    required=[inventory],
                    value=len(appliances),
                    data=[
                        {"status": key, "count": value}
                        for key, value in Counter(a.status for a in appliances).items()
                    ],
                ),
                _widget(
                    operations,
                    latest,
                    widget_id="sites",
                    title="Sitios",
                    description="Ubicaciones únicas normalizadas desde el inventario.",
                    visualization="stat",
                    required=[inventory],
                    value=len(sites) or len({a.site for a in appliances if a.site}),
                ),
                _widget(
                    operations,
                    latest,
                    widget_id="software-versions",
                    title="Versiones ECOS",
                    description="Distribución de software informada por los equipos.",
                    visualization="bars",
                    required=[inventory],
                    data=[{"label": key, "value": value} for key, value in version_counts.items()],
                ),
            ],
        ),
        DashboardSection(
            id="network",
            title="Capacidades de red",
            widgets=[
                _widget(
                    operations,
                    latest,
                    widget_id="performance",
                    title="Rendimiento",
                    description="Valores numéricos normalizados desde las respuestas de rendimiento.",
                    visualization="timeseries",
                    required=[performance],
                    value=len(metrics),
                    unit="métricas",
                    data=metric_data,
                ),
                _widget(
                    operations,
                    latest,
                    widget_id="interfaces",
                    title="Interfaces",
                    description="Inventario y estado de interfaces cuando la API los expone.",
                    visualization="table",
                    required=["appliance.interfaces"],
                    value=interface_issues,
                    unit="con incidencia",
                    data=interface_rows,
                ),
                _widget(
                    operations,
                    latest,
                    widget_id="tunnels",
                    title="Túneles",
                    description="Estado de túneles SD-WAN publicado por los appliances.",
                    visualization="table",
                    required=["appliance.tunnels"],
                    value=tunnel_issues,
                    unit="con incidencia",
                    data=tunnel_rows,
                ),
                _widget(
                    operations,
                    latest,
                    widget_id="topology",
                    title="Topología",
                    description="Vista de relaciones disponible en el Orchestrator.",
                    visualization="status",
                    required=["orchestrator.topology"],
                ),
            ],
        ),
        DashboardSection(
            id="correlation",
            title="Correlación por sitio",
            widgets=[
                _widget(
                    operations,
                    latest,
                    widget_id="site-risk",
                    title="Riesgo por ubicación",
                    description="Une inventario, métricas y estados para priorizar sitios.",
                    visualization="table",
                    required=[inventory],
                    data=risk_rows,
                ),
                _widget(
                    operations,
                    latest,
                    widget_id="metric-alerts",
                    title="Métricas fuera de rango",
                    description="CPU, memoria, utilización, pérdida, latencia, jitter y errores.",
                    visualization="table",
                    required=[performance],
                    data=anomalies[:20],
                ),
            ],
        ),
        DashboardSection(
            id="evidence",
            title="Salud y evidencia API",
            widgets=[
                _widget(
                    operations,
                    latest,
                    widget_id="api-health",
                    title="Éxito API",
                    description="Porcentaje de llamadas recientes que terminaron correctamente.",
                    visualization="stat",
                    required=[],
                    value=api_health,
                    unit="%",
                    data=[{"ok": successful, "total": len(samples)}],
                )
            ],
        ),
    ]
    return DashboardRead(
        orchestrator_id=orchestrator.id,
        orchestrator_name=orchestrator.name,
        api_version=orchestrator.api_version,
        generated_at=datetime.now(UTC),
        sections=sections,
    )


def _all_sample_rows(samples: list[ApiSample], operation: str, preferred_key: str) -> list[dict]:
    rows: list[dict] = []
    seen_appliances = set()
    for sample in samples:
        if sample.operation_id != operation or sample.appliance_id in seen_appliances:
            continue
        seen_appliances.add(sample.appliance_id)
        rows.extend(_sample_rows(sample, preferred_key))
    return rows[:100]


def _state_issues(rows: list[dict]) -> int:
    healthy = {"up", "ok", "healthy", "connected", "active", "enabled", "1", "true"}
    issues = 0
    for row in rows:
        states = [
            str(value).lower()
            for key, value in row.items()
            if any(word in key.lower() for word in ("state", "status", "health"))
        ]
        if states and not any(value in healthy for value in states):
            issues += 1
    return issues


def _metric_anomalies(metrics: list[MetricPoint]) -> list[dict]:
    alerts = []
    for point in metrics:
        name = point.metric_name.lower()
        threshold = None
        severity = "warning"
        if any(word in name for word in ("loss", "drop")):
            threshold = 2
        elif "latency" in name or "rtt" in name:
            threshold = 100
        elif "jitter" in name:
            threshold = 30
        elif any(word in name for word in ("cpu", "memory", "utilization")):
            threshold = 85
        elif any(word in name for word in ("error", "failed")):
            threshold = 0
        if threshold is not None and point.value > threshold:
            if point.value > threshold * 1.5 or (threshold == 0 and point.value > 10):
                severity = "critical"
            alerts.append(
                {
                    "severity": severity,
                    "site": point.dimensions.get("site") or "Sin sitio",
                    "hostname": point.dimensions.get("hostname") or "Equipo",
                    "metric": point.metric_name,
                    "value": round(point.value, 2),
                    "unit": point.unit or "",
                    "threshold": threshold,
                }
            )
    return sorted(alerts, key=lambda item: (item["severity"] != "critical", -float(item["value"])))


def _age_minutes(value: datetime) -> float:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return round(max(0, (datetime.now(UTC) - value).total_seconds() / 60), 1)


def _operation_latency(samples: list[ApiSample]) -> list[dict]:
    grouped: dict[str, list[float]] = {}
    for item in samples:
        if item.duration_ms is not None:
            grouped.setdefault(item.operation_id, []).append(float(item.duration_ms))
    return sorted(
        ({"label": key, "value": round(mean(values), 1)} for key, values in grouped.items()),
        key=lambda item: -item["value"],
    )[:8]


def _risk_by_site(
    appliances: list[Appliance], anomalies: list[dict], interfaces: list[dict], tunnels: list[dict]
) -> list[dict]:
    counts = Counter(item.site or "Sin sitio" for item in appliances)
    alerts = Counter(str(item.get("site") or "Sin sitio") for item in anomalies)
    global_issues = _state_issues(interfaces) + _state_issues(tunnels)
    rows = []
    for site, appliance_count in counts.items():
        issue_count = alerts[site]
        score = max(0, 100 - issue_count * 8 - (global_issues * 3 if len(counts) == 1 else 0))
        rows.append(
            {
                "site": site,
                "appliances": appliance_count,
                "signals": issue_count,
                "health": score,
                "priority": "Alta" if score < 70 else "Media" if score < 90 else "Normal",
            }
        )
    return sorted(rows, key=lambda item: item["health"])


def _sample_rows(sample: ApiSample | None, preferred_key: str) -> list[dict]:
    if sample is None or not isinstance(sample.payload, dict):
        return []
    payload = sample.payload
    for key in (preferred_key, "items", "data", "result"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value[:50] if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = [item for item in value.values() if isinstance(item, dict)]
            if nested:
                return nested[:50]
    return [payload]


def _widget(
    available: set[str],
    latest: dict[str, ApiSample],
    *,
    widget_id: str,
    title: str,
    description: str,
    visualization: str,
    required: list[str],
    value=None,
    unit: str | None = None,
    data: list[dict] | None = None,
) -> DashboardWidget:
    missing = [operation for operation in required if operation not in available]
    source = next((latest.get(operation) for operation in required if latest.get(operation)), None)
    if missing:
        status = "unavailable"
        reason = f"La versión detectada no declara: {', '.join(missing)}"
    elif required and source is None:
        status = "waiting"
        reason = "Capacidad detectada; falta ejecutar la primera consulta."
    else:
        status = "ready"
        reason = None
    operation_id = (
        source.operation_id if source else (required[0] if required else "dashboard.api.health")
    )
    provenance = WidgetProvenance(
        sample_id=source.id if source else None,
        operation_id=operation_id,
        method=source.method if source else None,
        path=source.path if source else None,
        collected_at=source.created_at if source else None,
    )
    return DashboardWidget(
        id=widget_id,
        title=title,
        description=description,
        visualization=visualization,
        status=status,
        reason=reason,
        value=value,
        unit=unit,
        data=data or [],
        required_operations=required,
        provenance=provenance,
    )
