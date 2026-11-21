"""
SwasthyaVaani — Async LLM Client (Google Gemini)
Pluggable wrapper for structured extraction, danger checking, and readback.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from google import genai
from google.genai import types

from backend.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Async wrapper around Google Gemini for the ASHA visit agent."""

    def __init__(self) -> None:
        self._client: genai.Client | None = None
        self.model = settings.llm_model

    @property
    def client(self) -> genai.Client:
        if self._client is None:
            if not settings.gemini_api_key:
                raise RuntimeError("GEMINI_API_KEY is not set in environment or .env file.")
            self._client = genai.Client(api_key=settings.gemini_api_key)
        return self._client

    async def _generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Send a prompt to Gemini and return the text response."""
        models_to_try = [self.model]
        for candidate in ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]:
            if candidate not in models_to_try:
                models_to_try.append(candidate)

        for m in models_to_try:
            try:
                response = self.client.models.generate_content(
                    model=m,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=0.1,  # Low temp for structured extraction
                        max_output_tokens=2048,
                        response_mime_type="application/json",
                    ),
                )
                if response and response.text:
                    logger.info("Successfully generated structured response using model: %s", m)
                    return response.text
            except Exception as e:
                logger.warning("Model %s generation failed (%s) — trying fallback.", m, e)

        logger.warning("All Gemini models unavailable, using local rule-based fallback.")
        return self._fallback_rule_generation(system_prompt, user_prompt)

    def _fallback_rule_generation(self, system_prompt: str, user_prompt: str) -> str:
        """Local rule-based fallback when offline or in sandboxed test mode."""
        import re
        from agent.danger_detector import danger_detector

        lower = user_prompt.lower()

        # Check if this is a correction request
        if "correction" in system_prompt.lower() or "current record:" in lower:
            # Extract updated weight if present
            m_weight = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:kilo|kg|kilos|kilograms|kgs|ಕೆಜಿ|கிலோ|కిలో|किलो)\b", lower)
            if not m_weight:
                m_weight = re.search(r"(?:weight|vajan|wazan|thooka|thuka|edai|baruvu|वजन|ತೂಕ|ಎಡೆ|எடை|బరువు)\s*(?:is|hai|agide|irukku|undi|aahe|ahe)?\s*[:\s]*(\d+(?:[.,]\d+)?)", lower)
            if m_weight:
                val = float(m_weight.group(1).replace(",", "."))
                return json.dumps({"weight_kg": val})
            return json.dumps({})

        # Beneficiary mapping: check all 8 synthetic beneficiaries
        beneficiaries = [
            (["priya", "प्रिया", "ಪ್ರಿಯಾ", "பிரியா", "ప్రియా"], "SYN-ASHA-001", "Priya Devi"),
            (["meena", "மீனா", "ಮೀನಾ", "மீனா", "మీనా"], "SYN-ASHA-002", "Meena Kumari"),
            (["kavitha", "कविता", "ಕವಿತಾ", "கவிதா", "కవిత"], "SYN-ASHA-003", "Kavitha S"),
            (["lakshmi", "लक्ष्मी", "ಲಕ್ಷ್ಮಿ", "லட்சுமி", "లక్ష్మి"], "SYN-ASHA-004", "Lakshmi R"),
            (["sunita", "सुनिता", "सुनीता", "ಸುನಿತಾ", "சுனிதா", "సునితా"], "SYN-ASHA-005", "Sunita Bai"),
            (["anjali", "अंजली", "अंजलि", "ಅಂಜಲಿ", "அஞ்சலி", "అంజలి"], "SYN-ASHA-006", "Anjali Devi"),
            (["fatima", "फातिमा", "ಫಾತಿಮಾ", "பாத்திமா", "ఫాతిమా"], "SYN-ASHA-007", "Fatima Bee"),
            (["radha", "राधा", "ರಾಧಾ", "ராதா", "రాధా"], "SYN-ASHA-008", "Radha M"),
        ]
        ben_id = "SYN-ASHA-999"
        ben_name = None
        for aliases, bid, bname in beneficiaries:
            if any(alias in lower for alias in aliases):
                ben_id = bid
                ben_name = bname
                break

        # Visit type: ANC, PNC, HBNC, Immunisation, default General
        vt = "General"
        if any(w in lower for w in ("anc", "prenatal", "garbhavati", "pregnant", "ಗರ್ಭಿಣಿ", "கர்ப்பிணி", "గర్భిణి", "गर्भवती")):
            vt = "ANC"
        elif any(w in lower for w in ("pnc", "postpartum", "prasav", "delivery", "post delivery", "हेರಿಗೆ", "ಪ್ರಸವ", "பிரசவம்", "ప్రసవం", "प्रसूती")):
            vt = "PNC"
        elif any(w in lower for w in ("hbnc", "navjat", "newborn", "shishu", "नवजात", "ಶಿಶು")):
            vt = "HBNC"
        elif any(w in lower for w in ("immun", "tikakaran", "vaccination", "tika", "लसीकरण", "ಲಸಿಕೆ", "தடுப்பூசி", "టీకా")):
            vt = "Immunisation"

        # Weight: extract ONLY if spoken (kg/kilo/vajan/thooka/etc.); else None (NEVER 55.0)
        weight = None
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:kilo|kg|kilos|kilograms|kgs|ಕೆಜಿ|கிலோ|కిలో|किलो)(?:\b|\s|$)", lower)
        if not m:
            m = re.search(r"(?:weight|vajan|wazan|thooka|thuka|edai|baruvu|वजन|ತೂಕ|ಎಡೆ|எடை|బరువు)\s*(?:is|hai|agide|irukku|undi|aahe|ahe)?\s*[:\s]*(\d+(?:[.,]\d+)?)", lower)
        if m:
            try:
                w_val = float(m.group(1).replace(",", "."))
                if 0.5 <= w_val <= 150.0:
                    weight = w_val
            except (ValueError, TypeError):
                weight = None

        # Next visit date: extract ONLY if spoken; else None (NEVER "2026-12-10")
        next_visit_date = None
        m_date = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", lower)
        if m_date:
            next_visit_date = m_date.group(1)
        else:
            m_date_dmy = re.search(r"\b(\d{2})[/-](\d{2})[/-](\d{4})\b", lower)
            if m_date_dmy:
                next_visit_date = f"{m_date_dmy.group(3)}-{m_date_dmy.group(2)}-{m_date_dmy.group(1)}"

        # Follow-up tasks: extract ONLY if spoken; else [] (NEVER ["Check BP next visit"])
        follow_up_tasks = []
        if "bp check" in lower or "check bp" in lower or "bp jaanch" in lower or "bp parikshe" in lower:
            follow_up_tasks.append("Check BP")
        if "blood test" in lower or "khoon ki jaanch" in lower or "rakta parikshe" in lower:
            follow_up_tasks.append("Blood test")
        if "sonography" in lower or "ultrasound" in lower:
            follow_up_tasks.append("Ultrasound")

        # Vaccines & supplements
        vax_given = []
        if "tt-1" in lower or "tt 1" in lower:
            vax_given.append("TT-1")
        if "tt-2" in lower or "tt 2" in lower:
            vax_given.append("TT-2")
        if "bcg" in lower:
            vax_given.append("BCG")
        if "opv" in lower:
            vax_given.append("OPV-0")

        supps = []
        if "ifa" in lower:
            supps.append("IFA goli")
        if "calcium" in lower:
            supps.append("calcium goli")

        # Vaccinations due: extract ONLY if explicitly spoken; else [] (NEVER ["TT-2"])
        vaccinations_due = []
        m_due = re.search(r"(?:due|baaki|bakki)\s*(?:hai|is)?\s*[:\s]*([a-zA-Z0-9\-]+)", lower)
        if m_due:
            v = m_due.group(1).upper()
            if any(k in v for k in ("TT", "BCG", "PENTA", "OPV", "ROTA", "MEASLES", "MR", "JE")):
                vaccinations_due.append(v)

        # Danger signs check
        danger_signs = danger_detector.deterministic_check(user_prompt)
        danger_flag = len(danger_signs) > 0
        danger_signs_detected = [s["id"] for s in danger_signs]
        referral_action = danger_detector.get_referral_message("hi-IN") if danger_flag else None

        return json.dumps(
            {
                "beneficiary_id": ben_id,
                "beneficiary_name": ben_name,
                "visit_type": vt,
                "weight_kg": weight,
                "vaccinations_due": vaccinations_due,
                "vaccinations_given": vax_given,
                "supplements_given": supps,
                "next_visit_date": next_visit_date,
                "follow_up_tasks": follow_up_tasks,
                "danger_flag": danger_flag,
                "danger_signs_detected": danger_signs_detected,
                "referral_action": referral_action,
                "confirmed": False,
                "notes_summary": f"{vt} visit notes" if ben_name is None else f"{vt} visit for {ben_name}",
            }
        )

    @staticmethod
    def _extract_json_dict(text: str) -> dict[str, Any]:
        """Robustly parse JSON object from text, handling markdown fences and surrounding text."""
        if not text:
            return {}
        t = text.strip()
        if "```" in t:
            m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", t)
            if m:
                t = m.group(1).strip()
        try:
            val = json.loads(t)
            if isinstance(val, dict):
                return val
        except json.JSONDecodeError:
            pass
        start = t.find("{")
        end = t.rfind("}")
        if start != -1 and end > start:
            try:
                val = json.loads(t[start : end + 1])
                if isinstance(val, dict):
                    return val
            except json.JSONDecodeError:
                pass
        return {}

    @staticmethod
    def _extract_json_list(text: str) -> list[Any]:
        """Robustly parse JSON array from text, handling markdown fences."""
        if not text:
            return []
        t = text.strip()
        if "```" in t:
            m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", t)
            if m:
                t = m.group(1).strip()
        try:
            val = json.loads(t)
            if isinstance(val, list):
                return val
        except json.JSONDecodeError:
            pass
        start = t.find("[")
        end = t.rfind("]")
        if start != -1 and end > start:
            try:
                val = json.loads(t[start : end + 1])
                if isinstance(val, list):
                    return val
            except json.JSONDecodeError:
                pass
        return []

    async def extract_visit_record(
        self,
        transcript: str,
        language: str,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        """Extract a structured visit record from spoken notes."""
        response_text = await self._generate(system_prompt, user_prompt)
        res = self._extract_json_dict(response_text)
        if not res:
            logger.warning("LLM returned unparseable text for extraction: %s — trying fallback rule generator", response_text[:150])
            fallback_text = self._fallback_rule_generation(system_prompt, user_prompt)
            res = self._extract_json_dict(fallback_text)
        return res

    async def check_danger_signs(
        self,
        transcript: str,
        system_prompt: str,
        user_prompt: str,
    ) -> list[str]:
        """LLM-based danger sign check (supplementary to deterministic)."""
        response_text = await self._generate(system_prompt, user_prompt)
        return self._extract_json_list(response_text)

    async def generate_readback(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Generate a concise spoken read-back of a visit record."""
        return await self._generate(system_prompt, user_prompt)

    async def apply_correction(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        """Apply a spoken correction to an existing record."""
        response_text = await self._generate(system_prompt, user_prompt)
        res = self._extract_json_dict(response_text)
        if not res:
            fallback_text = self._fallback_rule_generation(system_prompt, user_prompt)
            res = self._extract_json_dict(fallback_text)
        return res


# Singleton
llm_client = LLMClient()
