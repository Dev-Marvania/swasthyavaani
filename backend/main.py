"""
SwasthyaVaani — FastAPI Application Entry Point
Minimal main.py: CORS, /health, mount routers only.
(Per collab-boundaries.md: no business logic or WS handlers here.)
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.db import db
from backend.routers import records, ws


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    # Startup
    await db.init_db()
    yield
    # Shutdown
    await db.close()


app = FastAPI(
    title="SwasthyaVaani",
    description="Voice Field Register for ASHA Workers — Gnani Voice Hackathon PS1",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS (allow all origins for hackathon demo) ───────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount Routers ─────────────────────────────────────────────────────────

app.include_router(records.router)
app.include_router(ws.router)

# ── Health Check ──────────────────────────────────────────────────────────


@app.get("/")
async def root():
    """Root endpoint with service overview and links."""
    return {
        "service": "SwasthyaVaani — Voice Field Register for ASHA Workers",
        "version": "0.1.0",
        "status": "online",
        "docs_url": "/docs",
        "live_mic_tester": "/demo",
        "health_check": "/health",
        "endpoints": {
            "websocket_voice": "/ws/voice?lang=hi-IN",
            "beneficiaries": "/api/beneficiaries",
            "records": "/api/records",
            "languages": "/api/languages",
            "dpdp_purge": "DELETE /api/admin/purge",
        },
    }


@app.get("/health")
async def health():
    """Simple health check endpoint."""
    return {
        "status": "ok",
        "service": "SwasthyaVaani",
        "environment": settings.app_env,
    }
