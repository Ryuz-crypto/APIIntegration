from collections import Counter
from datetime import UTC, datetime

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
        key for key, available in orchestrator.capabilities.get("operations", {}).items() if available
    }
    latest = {}
    for sample in samples:
        latest.setdefault(sample.operation_id, sample)

    inventory = "orchestrator.inventory.summary"
    performance = "appliance.performance"
    sites = [resource for resource in resources if resource.resource_type == "site"]
    version_counts = Counter(item.software_version or "Sin versión" for item in appliances)
    successful = sum(1 for item in samples if item.ok)
    health = round(successful * 100 / len(samples), 1) if samples else 0
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
                    data=[{"status": key, "count": value} for key, value in Counter(a.status for a in appliances).items()],
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
                ),
                _widget(
                    operations,
                    latest,
                    widget_id="tunnels",
                    title="Túneles",
                    description="Estado de túneles SD-WAN publicado por los appliances.",
                    visualization="table",
                    required=["appliance.tunnels"],
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
                    value=health,
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
    operation_id = source.operation_id if source else (required[0] if required else "dashboard.api.health")
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
