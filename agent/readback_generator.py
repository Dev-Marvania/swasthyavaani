"""
SwasthyaVaani — Readback Generator
Builds concise 1-2 sentence spoken confirmations for TTS.
"""

from __future__ import annotations

import logging

from agent.llm_client import llm_client
from agent.prompts import (
    READBACK_SYSTEM_PROMPT,
    READBACK_USER_PROMPT,
    SAVE_BLOCKED_SYSTEM_PROMPT,
    SAVE_BLOCKED_USER_PROMPT,
)
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
        Generate a brief conversational read-back of the visit record, repeating
        collected facts and politely asking for confirmation or any missing info.

        CRITICAL CLINICAL INVARIANT:
        If record.danger_flag is True, missing fields are completely suppressed!
        """
        # If in clinical danger state, suppress routine missing field text entirely
        missing = [] if record.danger_flag else (missing_fields or [])
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
            # Fallback: conversational readback
            return self._fallback_readback(record, missing, language)

    async def generate_save_blocked_notice(
        self,
        language: str,
        missing_fields: list[str],
    ) -> str:
        """
        Generate a spoken notice informing the worker that a record cannot be saved yet
        because essential details are missing and have not been marked N/A.
        """
        friendly_map = {
            "weight_kg": "vajan (weight)",
            "vaccinations": "tika (vaccination)",
            "next_visit_date": "agli tareekh (next visit)",
            "visit_type": "visit type",
        }
        missing_text = ", ".join(friendly_map.get(f, f) for f in missing_fields)

        try:
            notice = await llm_client.generate_readback(
                system_prompt=SAVE_BLOCKED_SYSTEM_PROMPT,
                user_prompt=SAVE_BLOCKED_USER_PROMPT.format(
                    language=language,
                    missing_fields_text=missing_text,
                ),
            )
            return notice.strip().strip('"')
        except Exception as e:
            logger.warning("Save-blocked LLM generation failed: %s", e)
            if language.startswith("kn"):
                return f"ದಾಖಲೆಯನ್ನು ಇನ್ನೂ ಉಳಿಸಲು ಸಾಧ್ಯವಿಲ್ಲ, ದಯವಿಟ್ಟು {missing_text} ತಿಳಿಸಿ ಅಥವಾ 'not applicable' ಎಂದು ಹೇಳಿ."
            elif language.startswith("ta"):
                return f"பதிவை சேமிக்க முடியாது, தயவுசெய்து {missing_text} குறிப்பிடவும் அல்லது 'not applicable' என சொல்லவும்."
            elif language.startswith("te"):
                return f"రికార్డు ఇంకా సేవ్ చేయలేము, దయచేసి {missing_text} చెప్పండి లేదా 'not applicable' అని అనండి."
            elif language.startswith("mr"):
                return f"नोंद अजून सेव्ह करता येणार नाही, कृपया {missing_text} सांगा किंवा 'not applicable' म्हणा."
            else:
                return f"Record abhi save nahi ho sakta kyunki {missing_text} darj nahi hua hai. Kripya {missing_text} bataiye, ya 'not applicable' boliye."

    def _fallback_readback(
        self,
        record: ASHAVisitRecord,
        missing_fields: Optional[list[str]] = None,
        language: str = "hi-IN",
    ) -> str:
        """Conversational fallback if LLM is unavailable."""
        name = record.beneficiary_name or record.beneficiary_id
        v_type = record.visit_type.value if hasattr(record.visit_type, "value") else str(record.visit_type)

        details = [f"{name} ka {v_type} visit note darj kiya hai"]
        if record.weight_kg:
            details.append(f"vajan {record.weight_kg} kilo")
        if record.vaccinations_given:
            if any(v.lower() in ("none", "n/a", "na") for v in record.vaccinations_given):
                details.append("koi vaccine nahi di gayi")
            else:
                details.append(f"{', '.join(record.vaccinations_given)} diya gaya")
        if record.supplements_given:
            details.append(f"{', '.join(record.supplements_given)} di gayi")

        text = ", ".join(details) + "."

        if missing_fields and not record.danger_flag:
            first_missing = missing_fields[0]
            if first_missing == "weight_kg":
                text += " Kya vajan liya tha, ya not applicable hai?"
            elif first_missing == "next_visit_date":
                text += " Kya agla appointment schedule hua hai?"
            else:
                text += f" Kya {first_missing} darj karna hai?"
        else:
            text += " Kya yeh details sahi hain?"

        return text


# Singleton
readback_generator = ReadbackGenerator()
