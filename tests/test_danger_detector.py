"""
Tests for the DangerDetector — deterministic keyword matching.
No LLM calls needed; tests the authoritative path that CANNOT be suppressed.
"""

from __future__ import annotations

import pytest

from agent.danger_detector import DangerDetector


@pytest.fixture
def detector():
    return DangerDetector()


class TestDeterministicDangerDetection:
    """Test deterministic keyword matching against danger_signs.json."""

    # ── Maternal Danger Signs ──────────────────────────────────────────

    def test_maternal_bleeding_english(self, detector: DangerDetector):
        text = "Patient has heavy bleeding since morning"
        results = detector.deterministic_check(text)
        ids = [r["id"] for r in results]
        assert "MAT_BLEEDING" in ids

    def test_maternal_bleeding_hindi(self, detector: DangerDetector):
        text = "Bahut khoon beh raha hai, khoon behna band nahi ho raha"
        results = detector.deterministic_check(text)
        ids = [r["id"] for r in results]
        assert "MAT_BLEEDING" in ids

    def test_maternal_convulsions_codemix(self, detector: DangerDetector):
        text = "Patient ko daura aaya tha, fits aa rahe hain"
        results = detector.deterministic_check(text)
        ids = [r["id"] for r in results]
        assert "MAT_CONVULSIONS" in ids

    def test_maternal_preeclampsia_english(self, detector: DangerDetector):
        text = "She has severe headache and blurred vision"
        results = detector.deterministic_check(text)
        ids = [r["id"] for r in results]
        assert "MAT_PRE_ECLAMPSIA" in ids

    def test_maternal_high_fever_hindi(self, detector: DangerDetector):
        text = "Usko bahut tez bukhar hai"
        results = detector.deterministic_check(text)
        ids = [r["id"] for r in results]
        assert "MAT_HIGH_FEVER" in ids

    def test_maternal_abdominal_pain(self, detector: DangerDetector):
        text = "Baby not moving, severe abdominal pain"
        results = detector.deterministic_check(text)
        ids = [r["id"] for r in results]
        assert "MAT_ABDOMINAL_PAIN_FM" in ids

    # ── Newborn Danger Signs ──────────────────────────────────────────

    def test_newborn_fever(self, detector: DangerDetector):
        text = "Bacche ko tez bukhar hai, newborn fever"
        results = detector.deterministic_check(text)
        ids = [r["id"] for r in results]
        assert "NB_FEVER_HYPOTHERMIA" in ids

    def test_newborn_poor_feeding_hindi(self, detector: DangerDetector):
        text = "Bacha doodh nahi pee raha hai"
        results = detector.deterministic_check(text)
        ids = [r["id"] for r in results]
        assert "NB_POOR_FEEDING" in ids

    def test_newborn_breathing(self, detector: DangerDetector):
        text = "Baby has fast breathing and chest indrawing"
        results = detector.deterministic_check(text)
        ids = [r["id"] for r in results]
        assert "NB_BREATHING" in ids

    def test_newborn_lethargy(self, detector: DangerDetector):
        text = "Baby is lethargic, weak cry, very limp"
        results = detector.deterministic_check(text)
        ids = [r["id"] for r in results]
        assert "NB_LETHARGY_CONVULSIONS" in ids

    def test_newborn_jaundice(self, detector: DangerDetector):
        text = "Yellow palms and umbilical pus"
        results = detector.deterministic_check(text)
        ids = [r["id"] for r in results]
        assert "NB_JAUNDICE_UMBILICAL" in ids

    # ── No Danger Signs ───────────────────────────────────────────────

    def test_no_danger_normal_visit(self, detector: DangerDetector):
        text = "Normal ANC checkup, weight 55 kg, IFA goli diya, next visit 2 weeks"
        results = detector.deterministic_check(text)
        assert len(results) == 0

    def test_no_danger_immunisation(self, detector: DangerDetector):
        text = "Baby ko BCG and OPV-0 diya, weight 3.2 kg"
        results = detector.deterministic_check(text)
        assert len(results) == 0

    # ── Multiple Danger Signs ─────────────────────────────────────────

    def test_multiple_danger_signs(self, detector: DangerDetector):
        text = "Patient has heavy bleeding and high fever, baby not moving"
        results = detector.deterministic_check(text)
        ids = [r["id"] for r in results]
        assert "MAT_BLEEDING" in ids
        assert "MAT_HIGH_FEVER" in ids
        assert "MAT_ABDOMINAL_PAIN_FM" in ids

    # ── Case Insensitivity ────────────────────────────────────────────

    def test_case_insensitive(self, detector: DangerDetector):
        text = "HEAVY BLEEDING detected"
        results = detector.deterministic_check(text)
        ids = [r["id"] for r in results]
        assert "MAT_BLEEDING" in ids

    # ── Kannada Keywords ──────────────────────────────────────────────

    def test_kannada_bleeding(self, detector: DangerDetector):
        text = "Uthirapokku agide"
        results = detector.deterministic_check(text)
        ids = [r["id"] for r in results]
        assert "MAT_BLEEDING" in ids

    # ── Tamil Keywords ────────────────────────────────────────────────

    def test_tamil_breathing(self, detector: DangerDetector):
        text = "Kuzhandhai ku moochu thinaral irukku"
        results = detector.deterministic_check(text)
        ids = [r["id"] for r in results]
        assert "NB_BREATHING" in ids
