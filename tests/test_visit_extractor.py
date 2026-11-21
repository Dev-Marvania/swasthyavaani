"""
Tests for VisitExtractor — LLM extraction logic (mocked).
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from agent.visit_extractor import VisitExtractor
from backend.models import ASHAVisitRecord, Language, VisitType


@pytest.fixture
def extractor():
    return VisitExtractor()


MOCK_EXTRACTION_RESPONSE = {
    "beneficiary_id": "SYN-ASHA-001",
    "beneficiary_name": "Priya Devi",
    "visit_type": "ANC",
    "weight_kg": 55.0,
    "vaccinations_due": ["TT-2"],
    "vaccinations_given": ["TT-1"],
    "supplements_given": ["IFA goli", "calcium goli"],
    "next_visit_date": "2026-12-05",
    "follow_up_tasks": ["Check BP next visit", "Ensure TT-2"],
    "danger_flag": False,
    "danger_signs_detected": [],
    "referral_action": None,
    "confirmed": False,
    "language": "hi-IN",
    "notes_summary": "Routine ANC visit, all normal",
}


class TestVisitExtractor:
    """Test visit extraction with mocked LLM responses."""

    @pytest.mark.asyncio
    async def test_extract_normal_visit(self, extractor: VisitExtractor):
        """Normal ANC visit should extract without danger flags."""
        with patch(
            "agent.llm_client.llm_client.extract_visit_record",
            new_callable=AsyncMock,
            return_value=MOCK_EXTRACTION_RESPONSE,
        ), patch(
            "agent.llm_client.llm_client.check_danger_signs",
            new_callable=AsyncMock,
            return_value=[],
        ):
            record, dangers, source = await extractor.extract(
                transcript="Priya Devi ka ANC checkup, weight 55 kg, TT-1 diya, IFA goli diya",
                language="hi-IN",
            )

            assert record is not None
            assert record.beneficiary_id == "SYN-ASHA-001"
            assert record.visit_type == VisitType.ANC
            assert record.weight_kg == 55.0
            assert record.danger_flag is False

    @pytest.mark.asyncio
    async def test_extract_with_danger_sign(self, extractor: VisitExtractor):
        """Visit with danger sign should trigger flag + referral."""
        danger_response = dict(MOCK_EXTRACTION_RESPONSE)
        danger_response["danger_flag"] = True
        danger_response["danger_signs_detected"] = ["MAT_BLEEDING"]

        with patch(
            "agent.llm_client.llm_client.extract_visit_record",
            new_callable=AsyncMock,
            return_value=danger_response,
        ), patch(
            "agent.llm_client.llm_client.check_danger_signs",
            new_callable=AsyncMock,
            return_value=["MAT_BLEEDING"],
        ):
            record, dangers, source = await extractor.extract(
                transcript="Priya Devi ko heavy bleeding ho raha hai, bahut khoon",
                language="hi-IN",
            )

            assert record is not None
            assert record.danger_flag is True
            assert "MAT_BLEEDING" in record.danger_signs_detected
            assert len(dangers) > 0  # Deterministic should catch this too

    @pytest.mark.asyncio
    async def test_extract_empty_response(self, extractor: VisitExtractor):
        """Empty LLM response should return None record."""
        with patch(
            "agent.llm_client.llm_client.extract_visit_record",
            new_callable=AsyncMock,
            return_value={},
        ), patch(
            "agent.llm_client.llm_client.check_danger_signs",
            new_callable=AsyncMock,
            return_value=[],
        ):
            record, dangers, source = await extractor.extract(
                transcript="...",
                language="hi-IN",
            )
            assert record is None

    @pytest.mark.asyncio
    async def test_apply_correction(self, extractor: VisitExtractor):
        """Voice correction should update only the specified field."""
        original = ASHAVisitRecord(
            beneficiary_id="SYN-ASHA-001",
            visit_type=VisitType.ANC,
            weight_kg=55.0,
            danger_flag=False,
            confirmed=False,
            language=Language.HI,
        )

        corrected_data = original.model_dump(mode="json")
        corrected_data["weight_kg"] = 52.8

        with patch(
            "agent.llm_client.llm_client.apply_correction",
            new_callable=AsyncMock,
            return_value=corrected_data,
        ):
            corrected = await extractor.apply_correction(
                record=original,
                correction_text="nahi, weight 52.8 kilo hai",
            )

            assert corrected is not None
            assert corrected.weight_kg == 52.8
            assert corrected.beneficiary_id == "SYN-ASHA-001"  # Unchanged
