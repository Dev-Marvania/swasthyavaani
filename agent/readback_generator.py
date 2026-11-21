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

    async def generate(self, record: ASHAVisitRecord, language: str) -> str:
        """
        Generate a brief spoken read-back of the visit record.

        Args:
            record: The extracted visit record to read back.
            language: BCP-47 language code (e.g., "hi-IN").

        Returns:
            A short spoken confirmation string in the specified language.
        """
        record_json = record.model_dump_json(indent=2)
        user_prompt = READBACK_USER_PROMPT.format(
            language=language,
            record_json=record_json,
        )
        try:
            readback = await llm_client.generate_readback(
                system_prompt=READBACK_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )
            return readback.strip().strip('"')
        except Exception as e:
            logger.error("Readback generation failed: %s", e)
            # Fallback: basic English readback
            return self._fallback_readback(record)

    def _fallback_readback(self, record: ASHAVisitRecord) -> str:
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
        return ". ".join(parts) + ". Please confirm."


# Singleton
readback_generator = ReadbackGenerator()
