from fastapi import APIRouter

from app.api.v1.endpoints import (
    audit_logs,
    auth,
    dashboard,
    evaluations,
    groups,
    health,
    preferences,
    providers,
    submissions,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(preferences.router)
api_router.include_router(providers.router)
api_router.include_router(groups.router)
api_router.include_router(submissions.router)
api_router.include_router(evaluations.router)
api_router.include_router(dashboard.router)
api_router.include_router(audit_logs.router)

