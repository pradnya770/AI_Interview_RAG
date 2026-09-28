from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.extensions import router as extensions_router
from app.api.v1.interviews import router as interviews_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.reports import router as reports_router
from app.api.v1.resumes import router as resumes_router

api_router = APIRouter()
for route_group in (health_router, auth_router, resumes_router, jobs_router,
                    interviews_router, reports_router, extensions_router):
    api_router.include_router(route_group)
