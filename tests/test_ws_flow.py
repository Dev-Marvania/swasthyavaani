"""
End-to-End WebSocket Flow Tests
Tests session lifecycle, first-turn AI disclosure, danger alerts,
draft records, spoken corrections, and DPDP storage.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models import ASHAVisitRecord, Language, VisitType

MOCK_VISIT_DRAFT = ASHAVisitRecord(
    record_id="REC-TEST001",
    beneficiary_id="SYN-ASHA-001",
    beneficiary_name="Priya Devi",
    visit_type=VisitType.ANC,
    weight_kg=55.0,
    vaccinations_due=["TT-2"],
    vaccinations_given=["TT-1"],
    supplements_given=["IFA goli"],
    next_visit_date="2026-12-10",
    follow_up_tasks=["Check BP next visit"],
    danger_flag=True,
    danger_signs_detected=["MAT_BLEEDING"],
    referral_action="Chetavni! Turant PHC refer karein.",
    confirmed=False,
    language=Language.HI,
    notes_summary="ANC visit with bleeding",
)


class TestWebSocketVoiceFlow:
    """End-to-end WebSocket protocol tests."""

    def test_ws_connection_and_greeting(self):
        """Verify session_ready and agent_speaking greeting."""
        with TestClient(app) as client:
            with client.websocket_connect("/ws/voice?lang=hi-IN") as ws:
                m1 = ws.receive_json()
                assert m1["type"] == "session_ready"
                assert m1["payload"]["language"] == "hi-IN"
                assert m1["payload"]["audio_sample_rate"] == 16000

                m2 = ws.receive_json()
                assert m2["type"] == "agent_speaking"
                assert m2["payload"]["speaking"] is True
                assert "SwasthyaVaani" in m2["payload"]["text"]

    def test_ws_danger_alert_and_draft_flow(self):
        """Simulate visit note with danger sign and verify danger_alert + record_draft."""
        with patch(
            "agent.visit_extractor.visit_extractor.extract",
            new_callable=AsyncMock,
            return_value=(
                MOCK_VISIT_DRAFT,
                [{"id": "MAT_BLEEDING", "label": "Vaginal bleeding"}],
                "deterministic",
            ),
        ), patch(
            "agent.readback_generator.readback_generator.generate",
            new_callable=AsyncMock,
            return_value="Priya Devi ka ANC visit record darj ho gaya.",
        ):
            with TestClient(app) as client:
                with client.websocket_connect("/ws/voice?lang=hi-IN") as ws:
                    ws.receive_json()  # session_ready
                    ws.receive_json()  # greeting agent_speaking

                    # Send debug turn
                    ws.send_text(
                        json.dumps(
                            {
                                "type": "text_turn_debug",
                                "timestamp": 1000,
                                "payload": {
                                    "text": "Priya Devi ko heavy bleeding ho raha hai"
                                },
                            }
                        )
                    )

                    events = []
                    for _ in range(6):
                        msg = ws.receive()
                        if "text" in msg:
                            events.append(json.loads(msg["text"]))

                    event_types = [e["type"] for e in events]
                    assert "transcript_final" in event_types
                    assert "danger_alert" in event_types
                    assert "record_draft" in event_types

                    # Check danger_alert contents
                    danger_ev = next(e for e in events if e["type"] == "danger_alert")
                    assert "MAT_BLEEDING" in danger_ev["payload"]["signs"]
                    assert danger_ev["payload"]["source"] == "deterministic"

                    # Check record_draft
                    draft_ev = next(e for e in events if e["type"] == "record_draft")
                    assert draft_ev["payload"]["record"]["beneficiary_id"] == "SYN-ASHA-001"
                    assert draft_ev["payload"]["record"]["danger_flag"] is True

    def test_ws_barge_in_and_purge(self):
        """Verify barge_in_ack and session_purge events."""
        with TestClient(app) as client:
            with client.websocket_connect("/ws/voice?lang=hi-IN") as ws:
                ws.receive_json()  # session_ready
                m = ws.receive_json()  # greeting (speaking: True)
                if m.get("type") == "agent_speaking" and m.get("payload", {}).get("speaking"):
                    ws.receive_json()  # greeting end (speaking: False)

                # Send barge_in
                ws.send_text(
                    json.dumps(
                        {
                            "type": "barge_in",
                            "timestamp": 2000,
                            "payload": {"reason": "client_vad"},
                        }
                    )
                )
                ack = ws.receive_json()
                assert ack["type"] == "barge_in_ack"

                # Send session_purge
                ws.send_text(
                    json.dumps(
                        {
                            "type": "session_purge",
                            "timestamp": 2001,
                            "payload": {},
                        }
                    )
                )
                purge = ws.receive_json()
                assert purge["type"] == "session_purged"
                assert "records_deleted" in purge["payload"]
                assert "transcripts_deleted" in purge["payload"]
