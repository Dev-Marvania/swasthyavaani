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
                    if language.startswith("kn"): friendly.append("ತೂಕ")
                    elif language.startswith("ta"): friendly.append("எடை")
                    elif language.startswith("te"): friendly.append("బరువు")
                    elif language.startswith("mr"): friendly.append("वजन")
                    elif language.startswith("en"): friendly.append("weight")
                    else: friendly.append("vajan")
                elif f == "vaccinations":
                    if language.startswith("kn"): friendly.append("ಲಸಿಕೆ")
                    elif language.startswith("ta"): friendly.append("தடுப்பூசி")
                    elif language.startswith("te"): friendly.append("టీకా")
                    elif language.startswith("mr"): friendly.append("लसीकरण")
                    elif language.startswith("en"): friendly.append("vaccination")
                    else: friendly.append("tika")
                elif f == "next_visit_date":
                    if language.startswith("kn"): friendly.append("ಮುಂದಿನ ಭೇಟಿ")
                    elif language.startswith("ta"): friendly.append("அடுத்த சந்திப்பு")
                    elif language.startswith("te"): friendly.append("తదుపరి సందర్శన")
                    elif language.startswith("mr"): friendly.append("पुढील तारीख")
                    elif language.startswith("en"): friendly.append("next visit date")
                    else: friendly.append("agli tareekh")
                else:
                    friendly.append(f)
            missing_text = ", ".join(friendly)
        else:
            missing_text = "None"

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
        def _get_field_name(f: str, lang: str) -> str:
            if f == "weight_kg":
                return "ತೂಕ" if lang.startswith("kn") else "எடை" if lang.startswith("ta") else "బరువు" if lang.startswith("te") else "वजन" if lang.startswith("mr") else "weight" if lang.startswith("en") else "vajan"
            if f == "vaccinations":
                return "ಲಸಿಕೆ" if lang.startswith("kn") else "தடுப்பூசி" if lang.startswith("ta") else "టీకా" if lang.startswith("te") else "लस" if lang.startswith("mr") else "vaccination" if lang.startswith("en") else "tika"
            if f == "next_visit_date":
                return "ಮುಂದಿನ ಭೇಟಿ" if lang.startswith("kn") else "அடுத்த சந்திப்பு" if lang.startswith("ta") else "తదుపరి సందర్శన" if lang.startswith("te") else "पुढील तारीख" if lang.startswith("mr") else "next appointment" if lang.startswith("en") else "agli tareekh"
            return f

        missing_text = ", ".join(_get_field_name(f, language) for f in missing_fields)

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
        """Strictly monolingual conversational fallback if LLM is unavailable."""
        name = record.beneficiary_name or record.beneficiary_id
        v_type = record.visit_type.value if hasattr(record.visit_type, "value") else str(record.visit_type)

        if language.startswith("kn"):
            parts = [f"{name} ಅವರ {v_type} ತಪಾಸಣೆ ದಾಖಲಿಸಲಾಗಿದೆ"]
            if record.weight_kg:
                parts.append(f"ತೂಕ {record.weight_kg} ಕೆಜಿ")
            if record.vaccinations_given and not any(v.lower() in ("none", "n/a", "na") for v in record.vaccinations_given):
                parts.append(f"{', '.join(record.vaccinations_given)} ನೀಡಲಾಗಿದೆ")
            text = ", ".join(parts) + ". ಈ ಮಾಹಿತಿ ಸರಿಯಾಗಿದೆಯೇ?"
        elif language.startswith("ta"):
            parts = [f"{name} அவர்களின் {v_type} பரிசோதனை பதிவு செய்யப்பட்டது"]
            if record.weight_kg:
                parts.append(f"எடை {record.weight_kg} கிலோ")
            if record.vaccinations_given and not any(v.lower() in ("none", "n/a", "na") for v in record.vaccinations_given):
                parts.append(f"{', '.join(record.vaccinations_given)} செலுத்தப்பட்டது")
            text = ", ".join(parts) + ". இந்த தகவல் சரியானதா?"
        elif language.startswith("te"):
            parts = [f"{name} గారి {v_type} పరీక్ష నమోదు చేయబడింది"]
            if record.weight_kg:
                parts.append(f"బరువు {record.weight_kg} కిలోలు")
            if record.vaccinations_given and not any(v.lower() in ("none", "n/a", "na") for v in record.vaccinations_given):
                parts.append(f"{', '.join(record.vaccinations_given)} ఇవ్వబడింది")
            text = ", ".join(parts) + ". ఈ సమాచారం సరైనదేనా?"
        elif language.startswith("mr"):
            parts = [f"{name} यांची {v_type} तपासणी नोंदवली आहे"]
            if record.weight_kg:
                parts.append(f"वजन {record.weight_kg} किलो")
            if record.vaccinations_given and not any(v.lower() in ("none", "n/a", "na") for v in record.vaccinations_given):
                parts.append(f"{', '.join(record.vaccinations_given)} दिली आहे")
            text = ", ".join(parts) + ". ही माहिती बरोबर आहे का?"
        elif language.startswith("en"):
            parts = [f"Recorded {v_type} visit note for {name}"]
            if record.weight_kg:
                parts.append(f"weight {record.weight_kg} kg")
            if record.vaccinations_given and not any(v.lower() in ("none", "n/a", "na") for v in record.vaccinations_given):
                parts.append(f"vaccines given: {', '.join(record.vaccinations_given)}")
            text = ", ".join(parts) + ". Is this correct?"
        else: # Default Hindi / Hinglish
            parts = [f"{name} ka {v_type} visit note darj kiya hai"]
            if record.weight_kg:
                parts.append(f"vajan {record.weight_kg} kilo")
            if record.vaccinations_given and not any(v.lower() in ("none", "n/a", "na") for v in record.vaccinations_given):
                parts.append(f"{', '.join(record.vaccinations_given)} diya gaya")
            if record.supplements_given:
                parts.append(f"{', '.join(record.supplements_given)} di gayi")
            text = ", ".join(parts) + ". Kya yeh details sahi hain?"

        return text


# Singleton
readback_generator = ReadbackGenerator()
