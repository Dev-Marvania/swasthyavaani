"""
Comprehensive Synthetic Transcript QA Suite for SwasthyaVaani
Tests standard clinical intake, all 8 synthetic beneficiaries, missing field preservation,
multilingual code-mix, danger sign escalation, and guarded confirmation gating.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from agent.danger_detector import danger_detector
from agent.language_detector import detect_language
from agent.visit_extractor import VisitExtractor
from backend.main import app
from backend.models import ASHAVisitRecord, Language, VisitType


@pytest.fixture
def extractor():
    return VisitExtractor()


class TestAllSyntheticBeneficiaries:
    """Verify that all 8 registered synthetic beneficiaries resolve to exact IDs and names without defaulting to Priya Devi."""

    SYNTHETIC_TEST_CASES = [
        ("Sunita Bai ka pehla ANC checkup kiya hai, weight 54 kg hai.", "SYN-ASHA-005", "Sunita Bai", VisitType.ANC),
        ("Anjali Devi ke bacche Ravi ko 6 mahine ka vaccination lagaya.", "SYN-ASHA-006", "Anjali Devi", VisitType.IMMUNISATION),
        ("Fatima Bee ka second trimester ANC visit hua, IFA goli di.", "SYN-ASHA-007", "Fatima Bee", VisitType.ANC),
        ("Radha M ka navjat shishu HBNC visit kiya, baccha swasth hai.", "SYN-ASHA-008", "Radha M", VisitType.HBNC),
        ("Priya Devi ka ANC checkup hua, weight 55 kg.", "SYN-ASHA-001", "Priya Devi", VisitType.ANC),
        ("Meena Kumari ka prasav ke baad PNC checkup kiya.", "SYN-ASHA-002", "Meena Kumari", VisitType.PNC),
        ("Kavitha S third trimester ANC checkup, weight 60 kg.", "SYN-ASHA-003", "Kavitha S", VisitType.ANC),
        ("Lakshmi R post delivery checkup completed.", "SYN-ASHA-004", "Lakshmi R", VisitType.PNC),
    ]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("transcript,expected_id,expected_name,expected_vtype", SYNTHETIC_TEST_CASES)
    async def test_synthetic_beneficiary_resolution(
        self,
        extractor: VisitExtractor,
        transcript: str,
        expected_id: str,
        expected_name: str,
        expected_vtype: VisitType,
    ):
        result = await extractor.extract(transcript=transcript)
        assert result.record is not None
        assert result.record.beneficiary_id == expected_id, (
            f"Expected {expected_id} but got {result.record.beneficiary_id} (Never default to Priya Devi!)"
        )
        assert result.record.beneficiary_name == expected_name
        assert result.record.visit_type == expected_vtype

    @pytest.mark.asyncio
    async def test_no_beneficiary_mentioned_never_defaults_to_priya_devi(self, extractor: VisitExtractor):
        """When no beneficiary name is uttered, beneficiary_id must be SYN-ASHA-999 and name must be None."""
        transcript = "Routine checkup kiya, blood pressure normal hai, koi dikkat nahi."
        result = await extractor.extract(transcript=transcript)
        assert result.record is not None
        assert result.record.beneficiary_id == "SYN-ASHA-999"
        assert result.record.beneficiary_name is None, (
            f"Expected beneficiary_name to be None, got {result.record.beneficiary_name}"
        )


class TestUnmentionedFieldsPreservedAsNone:
    """Verify that unmentioned clinical fields remain None/empty rather than populating dummy defaults."""

    @pytest.mark.asyncio
    async def test_missing_weight_not_defaulted(self, extractor: VisitExtractor):
        """Unmentioned weight must stay None (never 55.0 kg) and be flagged in missing_fields."""
        transcript = "Sunita Bai ka ANC checkup kiya hai, koi dawai nahi di."
        result = await extractor.extract(transcript=transcript)
        assert result.record is not None
        assert result.record.weight_kg is None, (
            f"Expected weight_kg to be None, but got {result.record.weight_kg}"
        )
        assert "weight_kg" in result.missing_fields

    @pytest.mark.asyncio
    async def test_missing_next_visit_date_not_defaulted(self, extractor: VisitExtractor):
        """Unmentioned appointment date must stay None (never '2026-12-10') and be flagged in missing_fields."""
        transcript = "Fatima Bee ka ANC checkup kiya hai, weight 56 kg hai."
        result = await extractor.extract(transcript=transcript)
        assert result.record is not None
        assert result.record.next_visit_date is None, (
            f"Expected next_visit_date to be None, but got {result.record.next_visit_date}"
        )
        assert "next_visit_date" in result.missing_fields

    @pytest.mark.asyncio
    async def test_missing_tasks_and_vax_due_not_defaulted(self, extractor: VisitExtractor):
        """Unmentioned tasks and due vaccines must stay empty (never dummy defaults)."""
        transcript = "Radha M ka visit kiya, baccha normal hai."
        result = await extractor.extract(transcript=transcript)
        assert result.record is not None
        assert result.record.follow_up_tasks == [], (
            f"Expected follow_up_tasks to be [], but got {result.record.follow_up_tasks}"
        )
        assert result.record.vaccinations_due == [], (
            f"Expected vaccinations_due to be [], but got {result.record.vaccinations_due}"
        )


class TestMultilingualAndCodeMixIntake:
    """Verify multilingual speech intake and weight extraction across 6 supported languages."""

    @pytest.mark.asyncio
    async def test_kannada_kanglish_intake(self, extractor: VisitExtractor):
        """Kannada text with thooka (weight) and auto language detection."""
        transcript = "ಕವಿತಾ ಅವರಿಗೆ ಹೆರಿಗೆ ನಂತರದ ತಪಾಸಣೆ ಮಾಡಿದೆ, ತೂಕ 52 ಕೆಜಿ ಇದೆ."
        result = await extractor.extract(transcript=transcript, language="auto")
        assert result.detected_language == "kn-IN"
        assert result.record is not None
        assert result.record.beneficiary_id == "SYN-ASHA-003"
        assert result.record.weight_kg == 52.0

    @pytest.mark.asyncio
    async def test_tamil_tanglish_intake(self, extractor: VisitExtractor):
        """Tamil text with weight in kilograms and auto language detection."""
        transcript = "Inniku Priya ku checkup pannitom, weight 56 kg, kuzhandhai nalla irukku."
        result = await extractor.extract(transcript=transcript, language="auto")
        assert result.detected_language == "ta-IN"
        assert result.record is not None
        assert result.record.beneficiary_id == "SYN-ASHA-001"
        assert result.record.weight_kg == 56.0

    @pytest.mark.asyncio
    async def test_telugu_tenglish_intake(self, extractor: VisitExtractor):
        """Telugu text with weight and auto language detection."""
        transcript = "Ee roju Lakshmi ki checkup chesamu, baruvu 50 kg, pillalu bagunnaru."
        result = await extractor.extract(transcript=transcript, language="auto")
        assert result.detected_language == "te-IN"
        assert result.record is not None
        assert result.record.beneficiary_id == "SYN-ASHA-004"
        assert result.record.weight_kg == 50.0

    @pytest.mark.asyncio
    async def test_marathi_intake(self, extractor: VisitExtractor):
        """Marathi text with vajan (weight) and auto language detection."""
        transcript = "सुनिता बाई यांची तपासणी केली आहे आणि वजन 54 किलो आहे."
        result = await extractor.extract(transcript=transcript, language="auto")
        assert result.detected_language == "mr-IN"
        assert result.record is not None
        assert result.record.beneficiary_id == "SYN-ASHA-005"
        assert result.record.weight_kg == 54.0

    @pytest.mark.asyncio
    async def test_english_intake(self, extractor: VisitExtractor):
        """English text with kilograms and auto language detection (never defaulting to Hindi)."""
        transcript = "The patient Fatima Bee had a routine prenatal checkup today. Weight is 58 kilograms."
        result = await extractor.extract(transcript=transcript, language="auto")
        assert result.detected_language == "en-IN", (
            f"Expected en-IN language detection, got {result.detected_language}"
        )
        assert result.record is not None
        assert result.record.beneficiary_id == "SYN-ASHA-007"
        assert result.record.weight_kg == 58.0


class TestDangerSignsClinicalEscalation:
    """Verify deterministic danger sign detection and immediate PHC referral with zero medical advice."""

    @pytest.mark.asyncio
    async def test_maternal_bleeding_danger_sign(self, extractor: VisitExtractor):
        transcript = "Sunita Bai ko heavy bleeding ho rahi hai aur pet me bahut dard hai."
        result = await extractor.extract(transcript=transcript)
        assert result.record is not None
        assert result.record.danger_flag is True
        assert "MAT_BLEEDING" in result.record.danger_signs_detected
        assert result.record.referral_action is not None
        assert "PHC" in result.record.referral_action or "hospital" in result.record.referral_action.lower()

    @pytest.mark.asyncio
    async def test_maternal_convulsions_danger_sign(self, extractor: VisitExtractor):
        transcript = "Meena Kumari ko daure pad rahe hain aur behosh ho gayi hai."
        result = await extractor.extract(transcript=transcript)
        assert result.record is not None
        assert result.record.danger_flag is True
        assert any(s in result.record.danger_signs_detected for s in ("MAT_CONVULSIONS", "MAT_LOSS_CONSCIOUSNESS"))

    @pytest.mark.asyncio
    async def test_newborn_danger_sign(self, extractor: VisitExtractor):
        transcript = "Radha M ka newborn baby doodh nahi pee raha hai aur saans tez chal rahi hai."
        result = await extractor.extract(transcript=transcript)
        assert result.record is not None
        assert result.record.danger_flag is True
        assert any("NB_" in s for s in result.record.danger_signs_detected)

    def test_zero_medical_advice_rule(self):
        """Referral message must only instruct transport/referral, never medication dosages or home remedies."""
        for lang in ("hi-IN", "kn-IN", "ta-IN", "te-IN", "mr-IN", "en-IN"):
            ref_msg = danger_detector.get_referral_message(lang)
            lower_msg = ref_msg.lower()
            assert "paracetamol" not in lower_msg
            assert "ibuprofen" not in lower_msg
            assert "mg" not in lower_msg
            assert "tablet" not in lower_msg or "goli" not in lower_msg


class TestSaveBlockedGuard:
    """Verify that confirmation is guarded and blocked when mandatory clinical fields are missing."""

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

    def test_save_blocked_when_weight_and_appointment_missing(self):
        """Attempting to confirm a visit with missing mandatory fields triggers save_blocked event."""
        with TestClient(app) as client:
            with client.websocket_connect("/ws/voice?lang=hi-IN") as ws:
                # 1. session_ready
                ready = ws.receive_json()
                assert ready["type"] == "session_ready"

                # 2. Intake turn omitting weight and appointment date
                ws.send_text(
                    json.dumps(
                        {
                            "type": "text_turn_debug",
                            "timestamp": 1000,
                            "payload": {"text": "Sunita Bai ka ANC checkup kiya, koi dawai nahi di."},
                        }
                    )
                )

                # Drain turn response
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

                # 3. Premature confirmation attempt
                ws.send_text(
                    json.dumps(
                        {
                            "type": "text_turn_debug",
                            "timestamp": 2000,
                            "payload": {"text": "Save karo"},
                        }
                    )
                )

                # 4. Verify save_blocked event
                save_blocked_received = False
                while True:
                    msg = ws.receive()
                    if "text" in msg:
                        ev = json.loads(msg["text"])
                        if ev.get("type") == "save_blocked":
                            save_blocked_received = True
                            missing = ev["payload"]["missing_fields"]
                            assert "weight_kg" in missing
                            break

                assert save_blocked_received, "Expected save_blocked event for incomplete visit!"
