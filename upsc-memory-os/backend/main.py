"""UPSC Memory OS — FastAPI application entry point."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    print("=" * 60)
    print("  UPSC Memory OS — Starting up...")
    print("=" * 60)

    # ── Ensure data directories exist ────────────────────────────
    os.makedirs(settings.PDF_STORAGE_PATH, exist_ok=True)
    os.makedirs(settings.QDRANT_PATH, exist_ok=True)

    # ── Initialize embedding models (loads ~180MB on first run) ──
    print("[Startup] Loading embedding models...")
    from core.vector_store import init_models, init_collection
    init_models()
    print("[Startup] OK: Embedding models loaded")

    # ── Initialize Qdrant collection ─────────────────────────────
    init_collection()
    print("[Startup] OK: Qdrant collection ready")

    # ── Create database tables if needed ─────────────────────────
    from core.database import engine, Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)#create_all will check if tables exist and only create missing ones
    print("[Startup] OK: Database tables ready")

    # ── Start APScheduler ────────────────────────────────────────
    from services.prediction.jobs import setup_scheduler
    scheduler = setup_scheduler()
    scheduler.start()
    print("[Startup] OK: Scheduler started")

    print("=" * 60)
    print("  UPSC Memory OS — Ready!")
    print("=" * 60)

    yield

    # ── Shutdown ─────────────────────────────────────────────────
    print("[Shutdown] Cleaning up...")
    scheduler.shutdown()
    await engine.dispose()
    print("[Shutdown] OK: Done")


# ── Create app ───────────────────────────────────────────────────
app = FastAPI(
    title="UPSC Memory OS",
    description="AI-powered adaptive revision system for UPSC Civil Services",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ───────────────────────────────────────────────────
from api.routes.documents import router as documents_router
from api.routes.ask import router as ask_router
from api.routes.auth import router as auth_router
from api.routes.onboarding import router as onboarding_router
from api.routes.quiz import router as quiz_router
from api.routes.revision import router as revision_router

app.include_router(documents_router)
app.include_router(ask_router)
app.include_router(auth_router)
app.include_router(onboarding_router)
app.include_router(quiz_router)
app.include_router(revision_router)


# ── Health check ─────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "upsc-memory-os",
        "environment": settings.ENVIRONMENT,
    }


@app.get("/")
async def root():
    return {
        "message": "UPSC Memory OS API",
        "docs": "/docs",
        "health": "/health",
    }
