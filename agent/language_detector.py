"""
SwasthyaVaani — Automatic Indic Language Detector
Multi-tiered classifier for Indic languages (Hindi, Kannada, Tamil, Telugu, Marathi, English code-mix).
Supports Unicode script classification, STT metadata resolution, and colloquial code-mix keywords.
"""

from __future__ import annotations

import re
from typing import Optional

# Language definitions matching contracts/languages.json
SUPPORTED_LANGUAGES = {
    "hi-IN": "हिन्दी (Hindi / Hinglish)",
    "kn-IN": "ಕನ್ನಡ (Kannada / Kanglish)",
    "ta-IN": "தமிழ் (Tamil / Tanglish)",
    "te-IN": "తెలుగు (Telugu / Tenglish)",
    "mr-IN": "मराठी (Marathi)",
    "en-IN": "English (India)",
}

# ── 1. Unicode Script Character Ranges ──────────────────────────────────────────
SCRIPT_RANGES = {
    "kn-IN": re.compile(r"[\u0C80-\u0CFF]"),  # Kannada
    "ta-IN": re.compile(r"[\u0B80-\u0BFF]"),  # Tamil
    "te-IN": re.compile(r"[\u0C00-\u0C7F]"),  # Telugu
    "hi-IN": re.compile(r"[\u0900-\u097F]"),  # Devanagari (Hindi / Marathi)
}

# ── 2. Colloquial Indic Code-Mix Keywords (Romanized) ──────────────────────────
CODEMIX_KEYWORDS = {
    "kn-IN": {
        "hegide", "helabahudu", "nanna", "nimma", "thakshana", "maadi", "beku",
        "illa", "aagide", "mattu", "odayada", "thumba", "tumba", "kodu", "daakhalisuttene",
        "kooda", "avanu", "avalu", "idhu", "yenu", "neevu", "ivattu", "madide", "ide",
        "jwara", "makkalu", "nodu", "ge", "inda", "madidini",
    },
    "ta-IN": {
        "vanakkam", "sollungal", "pathivu", "kurippugalai", "arugil", "ulla",
        "anuppavum", "abaya", "arikuri", "thunbam", "irukku", "illai", "kudunga",
        "enakku", "unga", "avargal", "seithullen", "inniku", "kuzhandhai", "paaru", "pannitom",
    },
    "te-IN": {
        "namaskaram", "cheppandi", "namodu", "chestanu", "pramadakaramaina",
        "aalasyam", "cheyakunda", "ventane", "daggarlo", "undi", "ledu", "kadu",
        "unnaru", "chesanu", "chesamu", "pillalu", "choodu", "bagunnaru",
    },
    "mr-IN": {
        "namaskar", "bolun", "sanga", "nond", "karte", "dhokyache", "lakshan",
        "krupaya", "ushir", "karta", "rugnala", "tatkal", "javalchya", "aahe",
        "keli", "dya", "kasa", "aani", "mhanun", "vajan",
    },
    "hi-IN": {
        "namaste", "sahayak", "hoon", "sakti", "hain", "darj", "kar", "dungi",
        "khatre", "lakshan", "bina", "deri", "turant", "nazdeeki", "rahi", "raha",
        "hai", "tha", "thi", "diya", "liya", "karo", "theek", "sahi", "kripya",
        "bacche", "mareez", "bukhar", "dard", "khoon", "aaj", "kilo", "vajan",
    },
}


def detect_language(text: str, hint_lang: Optional[str] = None, stt_metadata: Optional[dict] = None) -> str:
    """
    Automatically detect the Indic language of the spoken text.

    Priority:
    1. STT metadata language if explicitly provided and valid.
    2. Direct native Indic script presence (Kannada, Tamil, Telugu, Devanagari).
    3. Distinct colloquial romanized code-mix keywords (Kanglish, Tanglish, etc.).
    4. Hint language from session (if valid and not "auto").
    5. Default to 'hi-IN'.
    """
    if stt_metadata and isinstance(stt_metadata, dict):
        meta_lang = stt_metadata.get("lang") or stt_metadata.get("language")
        if meta_lang and meta_lang in SUPPORTED_LANGUAGES and meta_lang != "auto":
            return meta_lang
    if not text or not text.strip():
        if hint_lang and hint_lang in SUPPORTED_LANGUAGES and hint_lang != "auto":
            return hint_lang
        return "hi-IN"

    clean_text = text.strip()

    # 1. Native Indic Script Check
    # Check Kannada, Tamil, Telugu specifically
    for lang, pattern in [("kn-IN", SCRIPT_RANGES["kn-IN"]), ("ta-IN", SCRIPT_RANGES["ta-IN"]), ("te-IN", SCRIPT_RANGES["te-IN"])]:
        if pattern.search(clean_text):
            return lang

    # Check Devanagari (could be Hindi or Marathi)
    if SCRIPT_RANGES["hi-IN"].search(clean_text):
        lower = clean_text.lower()
        if any(w in lower for w in ("आहे", "नाही", "केली", "नोंद", "लक्षण", "तातकाळ")):
            return "mr-IN"
        return "hi-IN"

    # 2. Romanized Code-Mix Lexical Check
    tokens = set(re.findall(r"\b[a-zA-Z]+\b", clean_text.lower()))
    if tokens:
        scores: dict[str, int] = {}
        for lang, vocab in CODEMIX_KEYWORDS.items():
            overlap = len(tokens.intersection(vocab))
            if overlap > 0:
                scores[lang] = overlap

        if scores:
            best_lang = max(scores, key=scores.get)
            return best_lang

    # 3. Use Hint / STT Metadata if provided and valid
    if hint_lang and hint_lang in SUPPORTED_LANGUAGES and hint_lang != "auto":
        return hint_lang

    return "hi-IN"


def get_language_label(lang_code: str) -> str:
    """Get the human-readable display label for a language code."""
    return SUPPORTED_LANGUAGES.get(lang_code, SUPPORTED_LANGUAGES["hi-IN"])
