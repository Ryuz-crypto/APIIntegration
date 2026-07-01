from fastapi import APIRouter

from app.api.routes import appliances, compatibility, health, orchestrators, system

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(system.router, prefix="/system", tags=["system"])
api_router.include_router(orchestrators.router, prefix="/orchestrators", tags=["orchestrators"])
api_router.include_router(appliances.router, prefix="/appliances", tags=["appliances"])
api_router.include_router(compatibility.router, prefix="/compatibility", tags=["compatibility"])
