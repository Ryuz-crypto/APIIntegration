from fastapi import APIRouter, Depends

from app.api.routes import (
    appliances,
    auth,
    compatibility,
    dashboard,
    health,
    orchestrators,
    samples,
    system,
    tryme,
)
from app.services.access_guard import access_guard

api_router = APIRouter(dependencies=[Depends(access_guard)])
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(system.router, prefix="/system", tags=["system"])
api_router.include_router(orchestrators.router, prefix="/orchestrators", tags=["orchestrators"])
api_router.include_router(appliances.router, prefix="/appliances", tags=["appliances"])
api_router.include_router(compatibility.router, prefix="/compatibility", tags=["compatibility"])
api_router.include_router(samples.router, prefix="/samples", tags=["samples"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(tryme.router, prefix="/try-me", tags=["try-me"])
