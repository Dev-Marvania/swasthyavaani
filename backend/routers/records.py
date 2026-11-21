"""
SwasthyaVaani — REST API Routers (Zone B)
Endpoints: beneficiaries, records, languages, admin purge.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from backend.db import db
from backend.models import ASHAVisitRecord

router = APIRouter()

# ── Load language config from frozen contract ──────────────────────────────

CONTRACTS_DIR = Path(__file__).resolve().parent.parent.parent / "contracts"


def _load_languages() -> dict:
    """Load contracts/languages.json (frozen contract)."""
    with open(CONTRACTS_DIR / "languages.json", encoding="utf-8") as f:
        return json.load(f)


# ── GET /demo ──────────────────────────────────────────────────────────────


@router.get("/demo", response_class=HTMLResponse)
async def live_mic_demo():
    """Serves the live laptop microphone testing interface."""
    demo_path = Path(__file__).resolve().parent.parent.parent / "scripts" / "test_mic.html"
    with open(demo_path, encoding="utf-8") as f:
        return f.read()


# ── GET /api/beneficiaries ─────────────────────────────────────────────────


@router.get("/api/beneficiaries")
async def list_beneficiaries():
    """Return all synthetic beneficiaries."""
    beneficiaries = await db.get_beneficiaries()
    return {"beneficiaries": beneficiaries}


# ── GET /api/records ───────────────────────────────────────────────────────


@router.get("/api/records")
async def list_records():
    """Return all saved visit records (decrypted)."""
    records = await db.get_records()
    return {"records": [r.model_dump(mode="json") for r in records]}


# ── GET /api/languages ─────────────────────────────────────────────────────


@router.get("/api/languages")
async def list_languages():
    """Return supported languages from the frozen contract."""
    lang_config = _load_languages()
    return lang_config


# ── DELETE /api/admin/purge ────────────────────────────────────────────────


@router.delete("/api/admin/purge")
async def purge_all_data():
    """
    DPDP compliance endpoint — purges ALL visit records and transcripts.
    Use after judging is complete.
    """
    result = await db.purge_all()
    return {
        "status": "purged",
        "records_deleted": result["records_deleted"],
        "transcripts_deleted": result["transcripts_deleted"],
    }
