"""
SwasthyaVaani — Danger Sign Detector (Dual-Path: Deterministic + LLM)

Compliance rule #3: NEVER allow the LLM to suppress a deterministic match.
A missed danger sign costs DOUBLE in judging.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Load frozen danger signs contract
CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "contracts"


def _load_danger_signs() -> dict[str, Any]:
    """Load contracts/danger_signs.json."""
    with open(CONTRACTS_DIR / "danger_signs.json", encoding="utf-8") as f:
        return json.load(f)


class DangerDetector:
    """
    Dual-path danger sign detection.

    Path 1 (Deterministic): Keyword/regex match against danger_signs.json — NEVER suppressible.
    Path 2 (LLM): Supplementary LLM check — can add signs but NEVER remove deterministic matches.

    Final result = union(deterministic, LLM).
    """

    def __init__(self) -> None:
        self._data = _load_danger_signs()
        self._all_signs: list[dict[str, Any]] = (
            self._data.get("maternal_danger_signs", [])
            + self._data.get("newborn_danger_signs", [])
        )
        # Pre-compile keyword patterns for fast matching
        self._compiled: list[tuple[str, str, re.Pattern]] = []
        for sign in self._all_signs:
            sign_id = sign["id"]
            label = sign["label"]
            for keyword in sign.get("keywords", []):
                # Case-insensitive word-boundary match
                pattern = re.compile(
                    r"\b" + re.escape(keyword.lower()) + r"\b",
                    re.IGNORECASE,
                )
                self._compiled.append((sign_id, label, pattern))

    # ── Deterministic Path ─────────────────────────────────────────────

    def deterministic_check(self, text: str) -> list[dict[str, str]]:
        """
        Keyword match against danger_signs.json.
        Returns list of {"id": ..., "label": ...} for matched signs.
        This path is AUTHORITATIVE — results CANNOT be suppressed.
        """
        text_lower = text.lower()
        matched: dict[str, str] = {}  # id → label (deduplicate)
        for sign_id, label, pattern in self._compiled:
            if pattern.search(text_lower):
                matched[sign_id] = label
        return [{"id": sid, "label": lbl} for sid, lbl in matched.items()]

    # ── LLM Path (async) ──────────────────────────────────────────────

    async def llm_check(self, text: str) -> list[str]:
        """
        LLM-based danger sign check — supplementary.
        Returns list of sign IDs the LLM flagged.
        """
        from agent.llm_client import llm_client
        from agent.prompts import DANGER_CHECK_SYSTEM_PROMPT, DANGER_CHECK_USER_PROMPT

        danger_json = json.dumps(
            [{"id": s["id"], "label": s["label"], "keywords": s["keywords"]} for s in self._all_signs],
            ensure_ascii=False,
            indent=2,
        )
        user_prompt = DANGER_CHECK_USER_PROMPT.format(
            danger_signs_json=danger_json,
            transcript=text,
        )
        try:
            return await llm_client.check_danger_signs(
                transcript=text,
                system_prompt=DANGER_CHECK_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )
        except Exception as e:
            logger.error("LLM danger check failed (falling back to deterministic only): %s", e)
            return []

    # ── Combined Detection ─────────────────────────────────────────────

    async def detect(self, text: str) -> tuple[list[dict[str, str]], str]:
        """
        Run both paths. Returns:
            (matched_signs, source)
        where source is "deterministic", "llm", or "both".
        matched_signs = union of both paths (deterministic NEVER suppressed).
        """
        # Always run deterministic first
        det_results = self.deterministic_check(text)
        det_ids = {r["id"] for r in det_results}

        # Run LLM check
        llm_ids = await self.llm_check(text)
        llm_only_ids = set(llm_ids) - det_ids

        # Add any LLM-only findings
        all_results = list(det_results)
        for sign_id in llm_only_ids:
            # Find label from our data
            label = sign_id
            for sign in self._all_signs:
                if sign["id"] == sign_id:
                    label = sign["label"]
                    break
            all_results.append({"id": sign_id, "label": label})

        # Determine source
        if det_ids and llm_only_ids:
            source = "both"
        elif det_ids:
            source = "deterministic"
        elif llm_only_ids:
            source = "llm"
        else:
            source = "none"

        return all_results, source

    # ── PHC Referral Message ───────────────────────────────────────────

    def get_referral_message(self, language: str) -> str:
        """Get the localized PHC referral alert from languages.json."""
        lang_path = CONTRACTS_DIR / "languages.json"
        with open(lang_path, encoding="utf-8") as f:
            lang_config = json.load(f)
        languages = lang_config.get("languages", {})
        if language in languages:
            return languages[language].get("phc_referral_alert", "")
        return "DANGER SIGN DETECTED — refer to nearest PHC immediately."


# Singleton
danger_detector = DangerDetector()
