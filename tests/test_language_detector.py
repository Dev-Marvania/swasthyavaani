"""Unit tests for the multilingual Indic language detector."""

import pytest
from agent.language_detector import detect_language, get_language_label, SUPPORTED_LANGUAGES


def test_script_detection_devanagari_hindi():
    text = "प्रिया देवी का एएनसी चेकअप किया है।"
    assert detect_language(text) == "hi-IN"


def test_script_detection_devanagari_marathi():
    text = "प्रिया देवी यांची तपासणी केली आहे आणि वजन चाळीस किलो आहे."
    assert detect_language(text) == "mr-IN"


def test_script_detection_kannada():
    text = "ಕವಿತಾ ಅವರಿಗೆ ಹೆರಿಗೆ ನಂತರದ ತಪಾಸಣೆ ಮಾಡಿದೆ, ತೂಕ 52 ಕೆಜಿ ಇದೆ."
    assert detect_language(text) == "kn-IN"


def test_script_detection_tamil():
    text = "பிரியா தேவிக்கு பிரசவத்திற்கு முந்தைய பரிசோதனை செய்யப்பட்டது."
    assert detect_language(text) == "ta-IN"


def test_script_detection_telugu():
    text = "ప్రియా దేవికి గర్భధారణ పరీక్ష పూర్తయింది."
    assert detect_language(text) == "te-IN"


def test_code_mix_romanized_kannada():
    text = "Ivattu Priya ge checkup madide, tumba jwara ide."
    assert detect_language(text) == "kn-IN"


def test_code_mix_romanized_tamil():
    text = "Inniku Priya ku checkup pannitom, kuzhandhai nalla irukku."
    assert detect_language(text) == "ta-IN"


def test_code_mix_romanized_telugu():
    text = "Ee roju Priya ki checkup chesamu, pillalu bagunnaru."
    assert detect_language(text) == "te-IN"


def test_code_mix_romanized_hindi():
    text = "Aaj Priya Devi ka ANC visit hai, weight 55 kilo hai."
    assert detect_language(text) == "hi-IN"


def test_stt_metadata_priority():
    # If STT explicitly passed kn-IN in metadata, detector should honor it
    assert detect_language("Hello visit note", stt_metadata={"lang": "kn-IN"}) == "kn-IN"


def test_default_fallback():
    assert detect_language("") == "hi-IN"
    assert detect_language("Normal routine checkup completed.") == "hi-IN"


def test_get_language_label():
    assert "Kannada" in get_language_label("kn-IN")
    assert "Hindi" in get_language_label("hi-IN")
    assert "Tamil" in get_language_label("ta-IN")
    assert "Telugu" in get_language_label("te-IN")
    assert "Marathi" in get_language_label("mr-IN")
