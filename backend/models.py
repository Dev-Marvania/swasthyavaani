"""
SwasthyaVaani — Pydantic v2 Data Models
Mirrors contracts/visit_record.schema.json exactly.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────────


class VisitType(str, Enum):
    """Allowed visit types from the schema."""

    ANC = "ANC"
    PNC = "PNC"
    HBNC = "HBNC"
    IMMUNISATION = "Immunisation"
    GENERAL = "General"


class Language(str, Enum):
    """Supported Indic languages + English."""

    HI = "hi-IN"
    KN = "kn-IN"
    TA = "ta-IN"
    TE = "te-IN"
    MR = "mr-IN"
    EN = "en-IN"


# ── Visit Record ───────────────────────────────────────────────────────────


class ASHAVisitRecord(BaseModel):
    """
    Structured ASHA home-visit record.
    Field constraints match contracts/visit_record.schema.json.
    """

    record_id: Optional[str] = None
    beneficiary_id: str = Field(..., pattern=r"^SYN-ASHA-[0-9]{3,}$")
    beneficiary_name: Optional[str] = None
    visit_type: VisitType
    weight_kg: Optional[float] = Field(None, ge=0.5, le=150.0)
    vaccinations_due: list[str] = Field(default_factory=list)
    vaccinations_given: list[str] = Field(default_factory=list)
    supplements_given: list[str] = Field(default_factory=list)
    next_visit_date: Optional[str] = None  # ISO date string
    follow_up_tasks: list[str] = Field(default_factory=list)
    danger_flag: bool = False
    danger_signs_detected: list[str] = Field(default_factory=list)
    referral_action: Optional[str] = None
    confirmed: bool = False
    language: Language = Language.HI
    notes_summary: Optional[str] = None

    model_config = {"extra": "forbid"}


# ── WebSocket Event Models ─────────────────────────────────────────────────


class WSEvent(BaseModel):
    """Base WebSocket JSON control frame."""

    type: str
    timestamp: int  # epoch_ms
    payload: dict = Field(default_factory=dict)


class SessionStartPayload(BaseModel):
    """Payload for session_start event."""

    language: Language = Language.HI
    mode: str = "vad"  # "vad" | "ptt"


class DangerAlertPayload(BaseModel):
    """Payload for danger_alert server event."""

    signs: list[str]
    labels: list[str]
    message: str
    source: str  # "deterministic" | "llm" | "both"


class RecordDraftPayload(BaseModel):
    """Payload for record_draft server event."""

    record: ASHAVisitRecord


class RecordConfirmedPayload(BaseModel):
    """Payload for record_confirmed server event."""

    record: ASHAVisitRecord
    saved_id: str
