"""
SwasthyaVaani — Visit Extractor
Orchestrates LLM extraction + Pydantic validation for visit records.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from agent.danger_detector import danger_detector
from agent.language_detector import detect_language
from agent.llm_client import llm_client
from agent.prompts import (
    CORRECTION_SYSTEM_PROMPT,
    CORRECTION_USER_PROMPT,
    VISIT_EXTRACTION_SYSTEM_PROMPT,
    VISIT_EXTRACTION_USER_PROMPT,
)
from backend.models import ASHAVisitRecord, VisitType

logger = logging.getLogger(__name__)


class ExtractionResult:
    """
    Rich container for extraction output.
    Maintains 3-tuple iteration compatibility (record, danger_signs, danger_source)
    while exposing missing_fields, detected_language, and na_fields attributes.
    """

    def __init__(
        self,
        record: Optional[ASHAVisitRecord],
        danger_signs: list[dict],
        danger_source: str,
        missing_fields: Optional[list[str]] = None,
        detected_language: str = "hi-IN",
        na_fields: Optional[set[str]] = None,
    ) -> None:
        self.record = record
        self.danger_signs = danger_signs
        self.danger_source = danger_source
        self.missing_fields = missing_fields or []
        self.detected_language = detected_language
        self.na_fields = na_fields or set()

    def __iter__(self):
        return iter((self.record, self.danger_signs, self.danger_source))


class VisitExtractor:
    """
    Extracts a structured ASHAVisitRecord from spoken transcript.
    Applies danger detection and handles voice corrections.
    """

    def _sanitize_record_dict(
        self,
        raw: dict[str, Any],
        transcript: str,
        language: str,
    ) -> dict[str, Any]:
        """
        Sanitize raw LLM dictionary so it is guaranteed to pass ASHAVisitRecord validation.
        """
        data = dict(raw)
        lower_trans = transcript.lower()

        # 1. beneficiary_id: Must match ^SYN-ASHA-[0-9]{3,}$
        ben_id = str(data.get("beneficiary_id") or "")
        ben_name = data.get("beneficiary_name")

        beneficiaries = [
            (["priya", "प्रिया", "ಪ್ರಿಯಾ", "பிரியா", "ప్రియా"], "SYN-ASHA-001", "Priya Devi"),
            (["meena", "मीना", "ಮೀನಾ", "மீனா", "మీనా"], "SYN-ASHA-002", "Meena Kumari"),
            (["kavitha", "कविता", "ಕವಿತಾ", "கவிதா", "కవిత"], "SYN-ASHA-003", "Kavitha S"),
            (["lakshmi", "लक्ष्मी", "ಲಕ್ಷ್ಮಿ", "லட்சுமி", "లక్ష్మి"], "SYN-ASHA-004", "Lakshmi R"),
            (["sunita", "सुनिता", "सुनीता", "ಸುನಿತಾ", "சுனிதா", "సునితా"], "SYN-ASHA-005", "Sunita Bai"),
            (["anjali", "अंजली", "अंजलि", "ಅಂಜಲಿ", "அஞ்சலி", "అంజలి"], "SYN-ASHA-006", "Anjali Devi"),
            (["fatima", "फातिमा", "ಫಾತಿಮಾ", "பாத்திமா", "ఫాతిమా"], "SYN-ASHA-007", "Fatima Bee"),
            (["radha", "राधा", "ರಾಧಾ", "ராதா", "రాధా"], "SYN-ASHA-008", "Radha M"),
        ]

        # Check if transcript mentions any of the 8 registered synthetic beneficiaries
        matched = False
        for aliases, bid, bname in beneficiaries:
            if any(alias in lower_trans for alias in aliases):
                data["beneficiary_id"] = bid
                data["beneficiary_name"] = ben_name or bname
                matched = True
                break

        if not matched:
            if re.match(r"^SYN-ASHA-[0-9]{3,}$", ben_id):
                data["beneficiary_id"] = ben_id
                data["beneficiary_name"] = ben_name
            else:
                data["beneficiary_id"] = "SYN-ASHA-999"
                data["beneficiary_name"] = None

        # 2. visit_type: Must be valid VisitType enum
        vt = str(data.get("visit_type") or "").upper()
        if any(w in lower_trans for w in ("anc", "prenatal", "garbhavati", "pregnant", "ಗರ್ಭಿಣಿ", "கர்ப்பிணி", "గర్భిణి", "गर्भवती")) or "ANC" in vt:
            data["visit_type"] = "ANC"
        elif any(w in lower_trans for w in ("pnc", "postpartum", "prasav", "delivery", "post delivery", "हेರಿಗೆ", "ಪ್ರಸವ", "பிரசவம்", "ప్రసవం", "प्रसूती")) or "PNC" in vt:
            data["visit_type"] = "PNC"
        elif any(w in lower_trans for w in ("hbnc", "navjat", "newborn", "shishu", "नवजात", "ಶಿಶು")) or "HBNC" in vt:
            data["visit_type"] = "HBNC"
        elif any(w in lower_trans for w in ("immun", "tikakaran", "vaccination", "tika", "लसीकरण", "ಲಸಿಕೆ", "தடுப்பூசி", "టీకా")) or "IMMUN" in vt:
            data["visit_type"] = "Immunisation"
        elif vt in ("ANC", "PNC", "HBNC", "IMMUNISATION", "GENERAL"):
            data["visit_type"] = vt.capitalize() if vt != "IMMUNISATION" else "Immunisation"
        else:
            data["visit_type"] = "General"

        # 3. weight_kg: Must be float in 0.5 to 150.0 or None
        w = data.get("weight_kg")
        if w is not None:
            try:
                w_val = float(w)
                if 0.5 <= w_val <= 150.0:
                    data["weight_kg"] = w_val
                else:
                    data["weight_kg"] = None
            except (ValueError, TypeError):
                data["weight_kg"] = None
        else:
            # Deterministic multilingual regex for weight mentions across English, Hindi, Kannada, Tamil, Telugu, Marathi
            m_w = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:kilo|kg|kilos|kilograms|kgs|ಕೆಜಿ|கிலோ|కిలో|किलो)(?:\b|\s|$)", lower_trans)
            if not m_w:
                m_w = re.search(r"(?:weight|vajan|wazan|thooka|thuka|edai|baruvu|वजन|ತೂಕ|ಎಡೆ|எடை|బరువు)\s*(?:is|hai|agide|irukku|undi|aahe|ahe)?\s*[:\s]*(\d+(?:[.,]\d+)?)", lower_trans)
            if m_w:
                try:
                    val = float(m_w.group(1).replace(",", "."))
                    if 0.5 <= val <= 150.0:
                        data["weight_kg"] = val
                except (ValueError, TypeError):
                    pass

        # 4. Ensure list fields are always lists, never None
        for k in ["vaccinations_due", "vaccinations_given", "supplements_given", "follow_up_tasks", "danger_signs_detected"]:
            val = data.get(k)
            if not isinstance(val, list):
                data[k] = [str(val)] if val is not None else []

        # Deterministic Clinical Keyword Extraction (Vaccines & Supplements)
        # Ensure vaccines explicitly spoken in transcript are captured even if LLM missed them
        vax_patterns = [
            (r"\btt[- ]?1\b", "TT-1"),
            (r"\btt[- ]?2\b", "TT-2"),
            (r"\btt[- ]?booster\b", "TT-Booster"),
            (r"\bbcg\b", "BCG"),
            (r"\bopv\b|\bpolio\b", "OPV"),
            (r"\bpentavalent\b|\bpenta[- ]?\d?\b", "Pentavalent"),
            (r"\brotavirus\b|\brota\b", "Rotavirus"),
            (r"\bmr[- ]?\d?\b|\bmeasles\b", "MR"),
            (r"\bhep(atitis)?[- ]?b\b", "Hepatitis B"),
            (r"\bvitamin[- ]?a\b|\bvit[- ]?a\b", "Vitamin A"),
        ]
        existing_vax = [str(x).lower() for x in (data.get("vaccinations_given") or [])]
        if "none" not in existing_vax:
            new_vax = list(data.get("vaccinations_given") or [])
            for pat, name in vax_patterns:
                if re.search(pat, lower_trans) and not any(name.lower() in v for v in existing_vax):
                    new_vax.append(name)
                    existing_vax.append(name.lower())
            data["vaccinations_given"] = new_vax

        # Deterministic Supplement Keywords
        supp_patterns = [
            (r"\bifa\b|\biron\b|\biron[- ]folic\b", "IFA tablets"),
            (r"\bcalcium\b", "Calcium tablets"),
            (r"\balbendazole\b|\bdeworming\b", "Albendazole"),
            (r"\bors\b", "ORS"),
            (r"\bzinc\b", "Zinc"),
        ]
        existing_supp = [str(x).lower() for x in (data.get("supplements_given") or [])]
        new_supp = list(data.get("supplements_given") or [])
        for pat, name in supp_patterns:
            if re.search(pat, lower_trans) and not any(name.lower() in s for s in existing_supp):
                new_supp.append(name)
                existing_supp.append(name.lower())
        data["supplements_given"] = new_supp

        # Check for explicit Not Applicable / None declarations in speech
        if any(w in lower_trans for w in ("koi vaccine nahi", "vaccine nahi", "no vaccine", "tika nahi", "koi injection nahi", "vaccine na", "vaccine n/a")):
            data["vaccinations_given"] = ["None"]

        if any(w in lower_trans for w in ("appointment nahi", "no appointment", "agla appointment nahi", "next visit nahi", "appointment na", "appointment n/a", "tareekh nahi")):
            data["next_visit_date"] = None
            tasks = list(data.get("follow_up_tasks") or [])
            if "Next visit: Not Applicable" not in tasks:
                tasks.append("Next visit: Not Applicable")
            data["follow_up_tasks"] = tasks

        # 5. Language enum
        data["language"] = language

        # 6. Filter out extra fields not defined in schema
        allowed_fields = {
            "record_id", "beneficiary_id", "beneficiary_name", "visit_type",
            "weight_kg", "vaccinations_due", "vaccinations_given", "supplements_given",
            "next_visit_date", "follow_up_tasks", "danger_flag", "danger_signs_detected",
            "referral_action", "confirmed", "language", "notes_summary"
        }
        return {k: v for k, v in data.items() if k in allowed_fields}

    def detect_missing_fields(
        self,
        record: ASHAVisitRecord,
        na_fields: Optional[set[str] | list[str]] = None,
    ) -> list[str]:
        """
        Identify essential clinical fields that were not collected in the spoken notes.
        Excludes any fields explicitly declared 'Not Applicable' (na_fields) or marked as 'None'.
        """
        missing: list[str] = []
        na_set = set(na_fields or [])

        # 1. Weight is essential for ANC, PNC, and Infant HBNC visits unless marked N/A
        if record.weight_kg is None and "weight_kg" not in na_set:
            missing.append("weight_kg")

        # 2. Vaccination status: resolved if given, due, marked None/N/A, or in na_set
        vax_given = [str(v).strip().lower() for v in (record.vaccinations_given or [])]
        vax_resolved = (
            (bool(record.vaccinations_given) and not all(v == "" for v in vax_given))
            or bool(record.vaccinations_due)
            or any(v in ("none", "n/a", "na", "koi nahi") for v in vax_given)
            or "vaccinations" in na_set
        )
        if not vax_resolved:
            if record.visit_type in (VisitType.ANC, VisitType.PNC, VisitType.HBNC, VisitType.IMMUNISATION):
                missing.append("vaccinations")

        # 3. Next visit date: resolved if date string present, marked in tasks, or in na_set
        tasks_lower = [str(t).lower() for t in (record.follow_up_tasks or [])]
        appt_resolved = (
            bool(record.next_visit_date)
            or "next_visit_date" in na_set
            or any("not applicable" in t or "not scheduled" in t for t in tasks_lower)
        )
        if not appt_resolved:
            if record.visit_type in (VisitType.ANC, VisitType.PNC, VisitType.HBNC):
                missing.append("next_visit_date")

        return missing

    async def extract(
        self,
        transcript: str,
        language: str = "auto",
    ) -> ExtractionResult:
        """
        Extract a visit record from the transcript with automatic language detection
        and missing field analysis.
        """
        # Resolve language automatically if "auto" or unspecified
        resolved_lang = detect_language(transcript, hint_lang=language if language != "auto" else None)

        user_prompt = VISIT_EXTRACTION_USER_PROMPT.format(
            language=resolved_lang,
            transcript=transcript,
        )
        raw_record = await llm_client.extract_visit_record(
            transcript=transcript,
            language=resolved_lang,
            system_prompt=VISIT_EXTRACTION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

        # Run dual-path danger detection
        danger_signs, danger_source = await danger_detector.detect(transcript)

        # Detect N/A declarations directly from transcript
        na_detected: set[str] = set()
        lower_trans = transcript.lower()
        if any(w in lower_trans for w in ("koi vaccine nahi", "vaccine nahi", "no vaccine", "tika nahi", "vaccine na", "vaccine n/a", "vaccine not applicable")):
            na_detected.add("vaccinations")
        if any(w in lower_trans for w in ("appointment nahi", "no appointment", "agla appointment nahi", "next visit nahi", "appointment na", "appointment n/a", "appointment not applicable")):
            na_detected.add("next_visit_date")
        if any(w in lower_trans for w in ("vajan nahi", "weight nahi", "no weight", "scale nahi", "weight na", "weight n/a", "weight not applicable")):
            na_detected.add("weight_kg")

        if not raw_record:
            logger.warning("LLM extraction returned empty result")
            return ExtractionResult(None, danger_signs, danger_source, [], resolved_lang, na_detected)

        # If LLM identified a specific detected_language, refine resolved_lang
        if raw_record.get("detected_language") in ("hi-IN", "kn-IN", "ta-IN", "te-IN", "mr-IN", "en-IN"):
            resolved_lang = raw_record["detected_language"]

        # Sanitize and merge danger detection
        sanitized = self._sanitize_record_dict(raw_record, transcript, resolved_lang)
        if danger_signs:
            sanitized["danger_flag"] = True
            existing_signs = sanitized.get("danger_signs_detected", [])
            all_sign_ids = list(
                dict.fromkeys(existing_signs + [s["id"] for s in danger_signs])
            )
            sanitized["danger_signs_detected"] = all_sign_ids
            if not sanitized.get("referral_action"):
                sanitized["referral_action"] = danger_detector.get_referral_message(resolved_lang)

        try:
            record = ASHAVisitRecord(**sanitized)
            missing_fields = self.detect_missing_fields(record, na_fields=na_detected)
            return ExtractionResult(record, danger_signs, danger_source, missing_fields, resolved_lang, na_detected)
        except Exception as e:
            logger.error("Pydantic validation failed: %s | Sanitized: %s", e, sanitized)
            return ExtractionResult(None, danger_signs, danger_source, [], resolved_lang, na_detected)

    async def apply_correction(
        self,
        record: ASHAVisitRecord,
        correction_text: str,
    ) -> Optional[ASHAVisitRecord]:
        """
        Apply a spoken voice correction to an existing record.
        E.g., "no, weight is 2.8 kilo" → updates weight_kg.
        """
        record_json = record.model_dump_json(indent=2)
        user_prompt = CORRECTION_USER_PROMPT.format(
            record_json=record_json,
            correction_text=correction_text,
        )
        corrected_data = await llm_client.apply_correction(
            system_prompt=CORRECTION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

        if not corrected_data:
            corrected_data = {}

        # Fallback weight extraction if LLM missed it
        if "weight_kg" not in corrected_data or corrected_data["weight_kg"] is None:
            m = re.search(r"(\d+(\.\d+)?)\s*(kilo|kg)", correction_text.lower())
            if m:
                corrected_data["weight_kg"] = float(m.group(1))

        # Merge corrected fields into existing record
        current_data = record.model_dump(mode="json")
        for k, v in corrected_data.items():
            if v is not None:
                current_data[k] = v

        sanitized = self._sanitize_record_dict(current_data, correction_text, record.language.value)
        try:
            return ASHAVisitRecord(**sanitized)
        except Exception as e:
            logger.error("Pydantic validation failed on correction: %s | Data: %s", e, sanitized)
            return record
        except Exception as e:
            logger.error("Pydantic validation failed on correction: %s", e)
            return None


# Singleton
visit_extractor = VisitExtractor()
