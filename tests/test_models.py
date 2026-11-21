"""
Tests for Pydantic models — validates against contracts/visit_record.schema.json.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.models import ASHAVisitRecord, Language, VisitType


class TestASHAVisitRecord:
    """Test the ASHAVisitRecord Pydantic model."""

    def test_valid_minimal_record(self):
        """Minimal required fields should pass validation."""
        record = ASHAVisitRecord(
            beneficiary_id="SYN-ASHA-001",
            visit_type=VisitType.ANC,
            danger_flag=False,
            confirmed=False,
            language=Language.HI,
        )
        assert record.beneficiary_id == "SYN-ASHA-001"
        assert record.visit_type == VisitType.ANC

    def test_valid_full_record(self):
        """All fields populated should pass validation."""
        record = ASHAVisitRecord(
            record_id="REC-12345678",
            beneficiary_id="SYN-ASHA-002",
            beneficiary_name="Meena Kumari",
            visit_type=VisitType.PNC,
            weight_kg=52.5,
            vaccinations_due=["BCG", "OPV-0"],
            vaccinations_given=["BCG"],
            supplements_given=["IFA goli"],
            next_visit_date="2026-12-01",
            follow_up_tasks=["Check newborn weight", "Give OPV-0"],
            danger_flag=True,
            danger_signs_detected=["NB_FEVER_HYPOTHERMIA"],
            referral_action="Refer to PHC immediately",
            confirmed=True,
            language=Language.HI,
            notes_summary="PNC visit, newborn has high fever",
        )
        assert record.danger_flag is True
        assert "NB_FEVER_HYPOTHERMIA" in record.danger_signs_detected

    def test_invalid_beneficiary_id_pattern(self):
        """beneficiary_id must match ^SYN-ASHA-[0-9]{3,}$."""
        with pytest.raises(ValidationError):
            ASHAVisitRecord(
                beneficiary_id="REAL-PATIENT-001",  # Wrong pattern
                visit_type=VisitType.ANC,
                danger_flag=False,
                confirmed=False,
                language=Language.HI,
            )

    def test_invalid_weight_too_low(self):
        """weight_kg must be >= 0.5."""
        with pytest.raises(ValidationError):
            ASHAVisitRecord(
                beneficiary_id="SYN-ASHA-001",
                visit_type=VisitType.HBNC,
                weight_kg=0.1,  # Too low
                danger_flag=False,
                confirmed=False,
                language=Language.HI,
            )

    def test_invalid_weight_too_high(self):
        """weight_kg must be <= 150.0."""
        with pytest.raises(ValidationError):
            ASHAVisitRecord(
                beneficiary_id="SYN-ASHA-001",
                visit_type=VisitType.GENERAL,
                weight_kg=200.0,  # Too high
                danger_flag=False,
                confirmed=False,
                language=Language.HI,
            )

    def test_invalid_visit_type(self):
        """visit_type must be one of the enum values."""
        with pytest.raises(ValidationError):
            ASHAVisitRecord(
                beneficiary_id="SYN-ASHA-001",
                visit_type="Surgery",  # Not in enum
                danger_flag=False,
                confirmed=False,
                language=Language.HI,
            )

    def test_no_extra_fields_allowed(self):
        """additionalProperties: false in schema."""
        with pytest.raises(ValidationError):
            ASHAVisitRecord(
                beneficiary_id="SYN-ASHA-001",
                visit_type=VisitType.ANC,
                danger_flag=False,
                confirmed=False,
                language=Language.HI,
                extra_field="should fail",  # Not in schema
            )

    def test_all_languages_valid(self):
        """All Language enum values should be accepted."""
        for lang in Language:
            record = ASHAVisitRecord(
                beneficiary_id="SYN-ASHA-001",
                visit_type=VisitType.ANC,
                danger_flag=False,
                confirmed=False,
                language=lang,
            )
            assert record.language == lang

    def test_all_visit_types_valid(self):
        """All VisitType enum values should be accepted."""
        for vt in VisitType:
            record = ASHAVisitRecord(
                beneficiary_id="SYN-ASHA-001",
                visit_type=vt,
                danger_flag=False,
                confirmed=False,
                language=Language.HI,
            )
            assert record.visit_type == vt

    def test_default_lists_are_empty(self):
        """List fields should default to empty lists."""
        record = ASHAVisitRecord(
            beneficiary_id="SYN-ASHA-001",
            visit_type=VisitType.ANC,
            danger_flag=False,
            confirmed=False,
            language=Language.HI,
        )
        assert record.vaccinations_due == []
        assert record.vaccinations_given == []
        assert record.supplements_given == []
        assert record.follow_up_tasks == []
        assert record.danger_signs_detected == []
