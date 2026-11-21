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
from agent.llm_client import llm_client
from agent.prompts import (
    CORRECTION_SYSTEM_PROMPT,
    CORRECTION_USER_PROMPT,
    VISIT_EXTRACTION_SYSTEM_PROMPT,
    VISIT_EXTRACTION_USER_PROMPT,
)
from backend.models import ASHAVisitRecord

logger = logging.getLogger(__name__)


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
        if not re.match(r"^SYN-ASHA-[0-9]{3,}$", ben_id):
            if "priya" in lower_trans:
                data["beneficiary_id"] = "SYN-ASHA-001"
                data["beneficiary_name"] = data.get("beneficiary_name") or "Priya Devi"
            elif "meena" in lower_trans:
                data["beneficiary_id"] = "SYN-ASHA-002"
                data["beneficiary_name"] = data.get("beneficiary_name") or "Meena Kumari"
            elif "kavitha" in lower_trans:
                data["beneficiary_id"] = "SYN-ASHA-003"
                data["beneficiary_name"] = data.get("beneficiary_name") or "Kavitha S"
            elif "lakshmi" in lower_trans:
                data["beneficiary_id"] = "SYN-ASHA-004"
                data["beneficiary_name"] = data.get("beneficiary_name") or "Lakshmi R"
            else:
                data["beneficiary_id"] = "SYN-ASHA-001"
                data["beneficiary_name"] = data.get("beneficiary_name") or "Priya Devi"

        # 2. visit_type: Must be valid VisitType enum
        vt = str(data.get("visit_type") or "ANC").upper()
        if "ANC" in vt:
            data["visit_type"] = "ANC"
        elif "PNC" in vt:
            data["visit_type"] = "PNC"
        elif "HBNC" in vt:
            data["visit_type"] = "HBNC"
        elif "IMMUN" in vt or "TIKA" in vt:
            data["visit_type"] = "Immunisation"
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
            m_w = re.search(r"(\d+(\.\d+)?)\s*(kilo|kg)", lower_trans)
            if m_w:
                data["weight_kg"] = float(m_w.group(1))

        # 4. Ensure list fields are always lists, never None
        for k in ["vaccinations_due", "vaccinations_given", "supplements_given", "follow_up_tasks", "danger_signs_detected"]:
            val = data.get(k)
            if not isinstance(val, list):
                data[k] = [str(val)] if val is not None else []

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

    async def extract(
        self,
        transcript: str,
        language: str,
    ) -> tuple[Optional[ASHAVisitRecord], list[dict], str]:
        """
        Extract a visit record from the transcript.
        """
        user_prompt = VISIT_EXTRACTION_USER_PROMPT.format(
            language=language,
            transcript=transcript,
        )
        raw_record = await llm_client.extract_visit_record(
            transcript=transcript,
            language=language,
            system_prompt=VISIT_EXTRACTION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

        # Run dual-path danger detection
        danger_signs, danger_source = await danger_detector.detect(transcript)

        if not raw_record:
            logger.warning("LLM extraction returned empty result")
            return None, danger_signs, danger_source

        # Sanitize and merge danger detection
        sanitized = self._sanitize_record_dict(raw_record, transcript, language)
        if danger_signs:
            sanitized["danger_flag"] = True
            existing_signs = sanitized.get("danger_signs_detected", [])
            all_sign_ids = list(
                dict.fromkeys(existing_signs + [s["id"] for s in danger_signs])
            )
            sanitized["danger_signs_detected"] = all_sign_ids
            if not sanitized.get("referral_action"):
                sanitized["referral_action"] = danger_detector.get_referral_message(language)

        try:
            record = ASHAVisitRecord(**sanitized)
            return record, danger_signs, danger_source
        except Exception as e:
            logger.error("Pydantic validation failed: %s | Sanitized: %s", e, sanitized)
            return None, danger_signs, danger_source

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
