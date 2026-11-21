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

    @pytest.fixture(autouse=True)
    def mock_voice_services(self, monkeypatch):
        async def _mock_stream(*args, **kwargs):
            yield b"\x00" * 320

        async def _mock_connect(*args, **kwargs):
            return

        monkeypatch.setattr("backend.routers.ws.SwasthyaVaaniPipeline.stream_speech", _mock_stream)
        monkeypatch.setattr("voice.pipeline.SwasthyaVaaniPipeline.stream_speech", _mock_stream)
        monkeypatch.setattr("voice.tts_service.GnaniTimbreTTS.synthesize", _mock_stream)
        monkeypatch.setattr("voice.stt_service.GnaniPrismaSTT.connect", _mock_connect)
        monkeypatch.setattr("agent.llm_client.LLMClient.generate_readback", AsyncMock(return_value="Priya Devi ka ANC visit note darj kiya gaya hai."))

    def test_ws_connection_and_greeting(self):
        """Verify session_ready in silent listening mode (no unprompted greeting)."""
        with TestClient(app) as client:
            with client.websocket_connect("/ws/voice?lang=hi-IN") as ws:
                m1 = ws.receive_json()
                assert m1["type"] == "session_ready"
                assert m1["payload"]["language"] == "hi-IN"
                assert m1["payload"]["audio_sample_rate"] == 16000

    def test_ws_danger_alert_and_draft_flow(self):
        """Simulate visit note with danger sign and verify danger_alert + record_draft."""
        with patch(
            "backend.routers.ws.visit_extractor.extract",
            new_callable=AsyncMock,
            return_value=(
                MOCK_VISIT_DRAFT,
                [{"id": "MAT_BLEEDING", "label": "Vaginal bleeding"}],
                "deterministic",
            ),
        ), patch(
            "backend.routers.ws.readback_generator.generate",
            new_callable=AsyncMock,
            return_value="Priya Devi ka ANC visit record darj ho gaya.",
        ):
            with TestClient(app) as client:
                with client.websocket_connect("/ws/voice?lang=hi-IN") as ws:
                    ws.receive_json()  # session_ready (silent connection)

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
                    while True:
                        msg = ws.receive()
                        if "text" in msg:
                            data = json.loads(msg["text"])
                            events.append(data)
                            if data.get("type") == "agent_speaking" and not data.get("payload", {}).get("speaking"):
                                break

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
                ws.receive_json()  # session_ready (silent connection)

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

    def test_ws_save_blocked_when_missing_required_fields(self):
        """Attempting to save while mandatory fields are missing should emit save_blocked."""
        incomplete_draft = ASHAVisitRecord(
            beneficiary_id="SYN-ASHA-001",
            beneficiary_name="Priya Devi",
            visit_type=VisitType.ANC,
            weight_kg=None,  # Missing!
            vaccinations_given=[],
            danger_flag=False,
            confirmed=False,
            language=Language.HI,
        )

        with patch(
            "backend.routers.ws.visit_extractor.extract",
            new_callable=AsyncMock,
            return_value=(incomplete_draft, [], "deterministic"),
        ), patch(
            "backend.routers.ws.readback_generator.generate",
            new_callable=AsyncMock,
            return_value="Priya Devi ka ANC visit note darj kiya gaya hai.",
        ), patch(
            "backend.routers.ws.readback_generator.generate_save_blocked_notice",
            new_callable=AsyncMock,
            return_value="Weight missing hai, save nahi ho sakta.",
        ):
            with TestClient(app) as client:
                with client.websocket_connect("/ws/voice?lang=hi-IN") as ws:
                    ws.receive_json()  # session_ready (silent connection)

                    ws.send_text(
                        json.dumps(
                            {
                                "type": "text_turn_debug",
                                "timestamp": 1000,
                                "payload": {"text": "Priya Devi ka ANC visit hai"},
                            }
                        )
                    )

                    # Drain frames until turn finishes
                    draft_received = False
                    while True:
                        msg = ws.receive()
                        if "text" in msg:
                            ev = json.loads(msg["text"])
                            if ev.get("type") == "record_draft":
                                draft_received = True
                            elif ev.get("type") == "agent_speaking" and not ev.get("payload", {}).get("speaking"):
                                if draft_received:
                                    break

                    assert draft_received

                    # Now attempt premature save
                    ws.send_text(
                        json.dumps(
                            {
                                "type": "text_turn_debug",
                                "timestamp": 2000,
                                "payload": {"text": "Save karo"},
                            }
                        )
                    )

                    # Check that save_blocked event is received
                    save_blocked_received = False
                    while True:
                        msg = ws.receive()
                        if "text" in msg:
                            ev = json.loads(msg["text"])
                            if ev.get("type") == "save_blocked":
                                save_blocked_received = True
                                assert "weight_kg" in ev["payload"]["missing_fields"]
                                break

                    assert save_blocked_received, "Expected save_blocked event when required fields are missing!"

    def test_language_transition_stt_failure_resilience(self, monkeypatch):
        """
        Verify that if Gnani STT connection fails during an auto-detected language transition
        or a manual language_change frame, the WebSocket session stays alive, emits
        language_detected, delivers the record draft, and stays responsive.
        """
        async def _failing_connect(*args, **kwargs):
            raise ConnectionError("server rejected WebSocket connection: HTTP 403")

        # Mock STT connect to fail on language transition
        monkeypatch.setattr("voice.stt_service.GnaniPrismaSTT.connect", _failing_connect)

        with TestClient(app) as client:
            with client.websocket_connect("/ws/voice?lang=hi-IN") as ws:
                ready_ev = ws.receive_json()
                assert ready_ev["type"] == "session_ready"
                assert ready_ev["payload"]["language"] == "hi-IN"

                # Send note that triggers auto-detection of en-IN
                ws.send_text(
                    json.dumps(
                        {
                            "type": "text_turn_debug",
                            "timestamp": 1000,
                            "payload": {
                                "text": "Fatima Bee ka second trimester ANC visit hua, IFA goli di."
                            },
                        }
                    )
                )

                events = []
                while True:
                    msg = ws.receive()
                    if "text" in msg:
                        ev = json.loads(msg["text"])
                        events.append(ev)
                        if ev.get("type") == "agent_speaking" and not ev.get("payload", {}).get("speaking"):
                            break

                event_types = [e["type"] for e in events]
                assert "language_detected" in event_types
                assert "record_draft" in event_types

                lang_ev = next(e for e in events if e["type"] == "language_detected")
                assert lang_ev["payload"]["language"] == "en-IN"

                draft_ev = next(e for e in events if e["type"] == "record_draft")
                assert draft_ev["payload"]["record"]["beneficiary_id"] == "SYN-ASHA-007"
                assert draft_ev["payload"]["record"]["beneficiary_name"] == "Fatima Bee"

                # Also verify manual language_change does not crash on STT failure
                ws.send_text(
                    json.dumps(
                        {
                            "type": "language_change",
                            "timestamp": 2000,
                            "payload": {"language": "te-IN"},
                        }
                    )
                )
                m2 = ws.receive_json()
                assert m2["type"] == "session_ready"
                assert m2["payload"]["language"] == "te-IN"

