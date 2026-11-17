from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from backend.routes.assessment_routes import router as assessment_router
from backend.routes.auth_routes import router as auth_router
from backend.routes.career_routes import router as career_router
from backend.routes.skill_gap_routes import router as skill_gap_router
from backend.routes.resume_routes import router as resume_router
from backend.routes.role_routes import router as role_router
from backend.routes.roadmap_routes import router as roadmap_router
from backend.routes.progress_routes import router as progress_router
from backend.admin.admin_routes import router as admin_router
from backend.services.persistence import persistence


def _validate_deployment_config() -> None:
    if os.getenv("APP_ENV", "development").lower() != "production":
        return

    admin_password = os.getenv("ADMIN_PASSWORD", "")
    if len(admin_password) < 16 or admin_password == "ChangeMe123!":
        raise RuntimeError("Production requires ADMIN_PASSWORD to be set to a unique value of at least 16 characters")
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("Production requires DATABASE_URL for persistent application state")


_validate_deployment_config()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if persistence is not None:
        await run_in_threadpool(persistence.initialize)
    yield

_allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000",
    ).split(",")
    if origin.strip()
]

app = FastAPI(
    title="AI Skill Gap Analyzer API",
    version="2.0.0",
    description="AI-powered personalized learning & skill gap analyzer for TNP platforms.",
    lifespan=lifespan,
)

if os.getenv("APP_ENV", "development").lower() == "production" and "*" in _allowed_origins:
    raise RuntimeError("Production ALLOWED_ORIGINS must not include '*'.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def persist_application_state(request, call_next):
    if persistence is None or not request.url.path.startswith("/api/"):
        return await call_next(request)

    connection = await run_in_threadpool(persistence.begin_request)
    try:
        await run_in_threadpool(persistence.load, connection)
        response = await call_next(request)
        await run_in_threadpool(persistence.save, connection)
        return response
    except Exception:
        await run_in_threadpool(persistence.rollback, connection)
        raise
    finally:
        await run_in_threadpool(persistence.close, connection)


# Mount frontend static files if directory exists
_frontend_path = Path(__file__).parent.parent.parent / "frontend"
if _frontend_path.exists():
    app.mount("/app", StaticFiles(directory=str(_frontend_path), html=True), name="frontend")


@app.get("/health")
def health_check() -> dict:
    if persistence is not None and not persistence.check():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    return {"status": "ok", "version": "2.0.0"}


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/app")


@app.get("/dashboard")
def dashboard_page() -> RedirectResponse:
    return RedirectResponse(url="/app/dashboard.html")


@app.get("/assessment")
def assessment_page() -> RedirectResponse:
    return RedirectResponse(url="/app/assessment.html")


@app.get("/roadmap")
def roadmap_page() -> RedirectResponse:
    return RedirectResponse(url="/app/roadmap.html")


@app.get("/resume")
def resume_page() -> RedirectResponse:
    return RedirectResponse(url="/app/resume.html")


@app.get("/admin")
def admin_page() -> RedirectResponse:
    return RedirectResponse(url="/app/admin.html")


@app.get("/index.html")
def legacy_home_page() -> RedirectResponse:
    return RedirectResponse(url="/")


@app.get("/dashboard.html")
def legacy_dashboard_page() -> RedirectResponse:
    return RedirectResponse(url="/dashboard")


@app.get("/assessment.html")
def legacy_assessment_page() -> RedirectResponse:
    return RedirectResponse(url="/assessment")


@app.get("/roadmap.html")
def legacy_roadmap_page() -> RedirectResponse:
    return RedirectResponse(url="/roadmap")


@app.get("/resume.html")
def legacy_resume_page() -> RedirectResponse:
    return RedirectResponse(url="/resume")


@app.get("/admin.html")
def legacy_admin_page() -> RedirectResponse:
    return RedirectResponse(url="/admin")


# ── Register all routers ─────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(career_router)
app.include_router(assessment_router)
app.include_router(skill_gap_router)
app.include_router(resume_router)
app.include_router(role_router)
app.include_router(roadmap_router)
app.include_router(progress_router)
app.include_router(admin_router)
