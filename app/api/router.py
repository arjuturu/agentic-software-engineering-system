from fastapi import APIRouter

from app.api.v1.approvals import router as approvals_router
from app.api.v1.artifacts import router as artifacts_router
from app.api.v1.audit import router as audit_router
from app.api.v1.health import router as health_router
from app.api.v1.workflows import router as workflows_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(workflows_router)
api_router.include_router(approvals_router)
api_router.include_router(artifacts_router)
api_router.include_router(audit_router)
