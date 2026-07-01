from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "dashboardapi_ec",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.timezone = "UTC"
celery_app.conf.task_routes = {
    "app.workers.tasks.poll_orchestrator": {"queue": "orchestrators"},
    "app.workers.tasks.poll_appliance": {"queue": "appliances"},
}
