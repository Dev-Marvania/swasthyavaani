"""
SwasthyaVaani — Readback Generator
Builds concise 1-2 sentence spoken confirmations for TTS.
"""

from __future__ import annotations

import logging

from agent.llm_client import llm_client
from agent.prompts import READBACK_SYSTEM_PROMPT, READBACK_USER_PROMPT
from backend.models import ASHAVisitRecord

logger = logging.getLogger(__name__)


class ReadbackGenerator:
    """
    Generates concise spoken read-back confirmations from visit records.
    Keeps output short (1-2 sentences) so the ASHA worker can confirm
    or correct while walking between houses.
    """

    async def generate(
        self,
        record: ASHAVisitRecord,
        language: str = "hi-IN",
        missing_fields: Optional[list[str]] = None,
    ) -> str:
        """
        Generate a brief spoken read-back of the visit record, including prompts
        for any missing essential fields.

        Args:
            record: The extracted visit record to read back.
            language: BCP-47 language code (e.g., "hi-IN").
            missing_fields: Optional list of field names that were not collected.

        Returns:
            A short spoken confirmation string in the specified language.
        """
        missing = missing_fields or []
        if missing:
            friendly = []
            for f in missing:
                if f == "weight_kg":
                    friendly.append("weight (वजन)")
                elif f == "vaccinations":
                    friendly.append("vaccination details (टीकाकरण)")
                elif f == "next_visit_date":
                    friendly.append("next visit date (अगली जांच तिथि)")
                else:
                    friendly.append(f)
            missing_text = ", ".join(friendly)
        else:
            missing_text = "None (all primary details collected)"

        record_json = record.model_dump_json(indent=2)
        user_prompt = READBACK_USER_PROMPT.format(
            language=language,
            record_json=record_json,
            missing_fields_text=missing_text,
        )
        try:
            readback = await llm_client.generate_readback(
                system_prompt=READBACK_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )
            return readback.strip().strip('"')
        except Exception as e:
            logger.error("Readback generation failed: %s", e)
            # Fallback: basic readback
            return self._fallback_readback(record, missing)

    def _fallback_readback(
        self,
        record: ASHAVisitRecord,
        missing_fields: Optional[list[str]] = None,
    ) -> str:
        """Simple English fallback if LLM is unavailable."""
        parts = [f"Visit for {record.beneficiary_id}"]
        if record.beneficiary_name:
            parts = [f"Visit for {record.beneficiary_name}"]
        parts.append(f"Type: {record.visit_type.value}")
        if record.weight_kg:
            parts.append(f"Weight: {record.weight_kg} kg")
        if record.vaccinations_given:
            parts.append(f"Vaccines given: {', '.join(record.vaccinations_given)}")
        if record.danger_flag:
            parts.append("DANGER SIGN DETECTED — refer to PHC immediately")
        if missing_fields:
            parts.append(f"Note: {', '.join(missing_fields)} were not collected, please collect them")
        return ". ".join(parts) + ". Please confirm."


# Singleton
readback_generator = ReadbackGenerator()
