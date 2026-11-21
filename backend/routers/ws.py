"""
SwasthyaVaani — WebSocket Voice Endpoint (Zone A)
Full real-time streaming voice orchestrator implementing contracts/ws_protocol.md.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from agent.danger_detector import danger_detector
from agent.language_detector import detect_language, get_language_label
from agent.readback_generator import readback_generator
from agent.visit_extractor import visit_extractor
from backend.db import db
from backend.models import ASHAVisitRecord
from voice.pipeline import SwasthyaVaaniPipeline

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Helpers ────────────────────────────────────────────────────────────────


def _ws_event(event_type: str, payload: dict[str, Any] | None = None) -> str:
    """Build a JSON control frame string per contracts/ws_protocol.md."""
    return json.dumps(
        {
            "type": event_type,
            "timestamp": int(time.time() * 1000),
            "payload": payload or {},
        }
    )


def _load_language_config() -> dict:
    """Load contracts/languages.json."""
    from pathlib import Path

    contracts = Path(__file__).resolve().parent.parent.parent / "contracts"
    with open(contracts / "languages.json", encoding="utf-8") as f:
        return json.load(f)


# ── WebSocket Endpoint ─────────────────────────────────────────────────────


@router.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket, lang: str = "auto"):
    """
    Main real-time voice streaming WebSocket.
    Supports automatic language detection and missing field spoken prompts.

    Handles:
    - Binary frames: 16 kHz 16-bit mono PCM chunks in both directions.
    - JSON frames: Session lifecycle, live transcripts, danger alerts,
      draft records, and DPDP purges per contracts/ws_protocol.md.
    """
    await websocket.accept()

    session_id = f"SES-{uuid.uuid4().hex[:12].upper()}"
    auto_detect_enabled = (lang == "auto")
    language = "hi-IN" if auto_detect_enabled else lang
    lang_config = _load_language_config()
    current_record: Optional[ASHAVisitRecord] = None
    current_missing_fields: list[str] = []
    session_na_fields: set[str] = set()
    session_asked_fields: set[str] = set()
    lock = asyncio.Lock()

    # ── Initialize Voice Pipeline ──────────────────────────────────────────

    async def on_stt_transcript(text: str, is_final: bool, detected_lang: str):
        """Callback from Gnani Prisma STT."""
        nonlocal current_record, language
        try:
            if not is_final:
                await websocket.send_text(
                    _ws_event("transcript_partial", {"text": text, "language": detected_lang})
                )
            else:
                await websocket.send_text(
                    _ws_event("transcript_final", {"text": text, "language": detected_lang})
                )
                # Process the finalized speech turn
                asyncio.create_task(process_text_turn(text, detected_lang or language))
        except Exception as err:
            logger.error("Error in on_stt_transcript callback: %s", err)

    pipeline = SwasthyaVaaniPipeline(
        on_transcript=on_stt_transcript,
        language=language,
    )

    try:
        await pipeline.initialize()
    except Exception as e:
        logger.warning("Gnani STT connection failed on init (offline/sandbox mode): %s", e)

    # ── 1. Send session_ready (Contract) ───────────────────────────────────

    await websocket.send_text(
        _ws_event(
            "session_ready",
            {
                "session_id": session_id,
                "language": "auto" if auto_detect_enabled else language,
                "audio_sample_rate": 16000,
            },
        )
    )

    # ── 2. Mandatory First-Turn AI Disclosure (Compliance Rule #1) ──────────

    languages = lang_config.get("languages", {})
    greeting = ""
    if auto_detect_enabled:
        greeting = "Namaste! Main SwasthyaVaani AI sahayak hoon. Aap kisi bhi bhasha mein bol sakti hain, main notes darj kar dungi."
    elif language in languages:
        greeting = languages[language].get("ai_disclosure_greeting", "")

    if greeting:
        await websocket.send_text(
            _ws_event(
                "agent_speaking",
                {"speaking": True, "text": greeting},
            )
        )

        # Synthesize and stream greeting audio if connected
        try:
            async for pcm_chunk in pipeline.stream_speech(greeting):
                await websocket.send_bytes(pcm_chunk)
        except Exception as e:
            logger.debug("Greeting speech streaming skipped or failed: %s", e)
        finally:
            await websocket.send_text(
                _ws_event(
                    "agent_speaking",
                    {"speaking": False, "text": ""},
                )
            )

    # ── Helper: Process Text Turn (STT Final or Debug Turn) ────────────────

    async def process_text_turn(text: str, active_lang: str):
        """Runs danger detection, LLM extraction/correction, readback, and audio streaming."""
        nonlocal current_record, current_missing_fields, language, session_na_fields, session_asked_fields
        async with lock:
            # 1. Save transcript encrypted for DPDP
            try:
                await db.save_transcript(session_id, text)
            except Exception as e:
                logger.warning("Failed to save transcript: %s", e)

            lower = text.lower().strip()

            # 2. Check for explicit spoken "Not Applicable" / "None" declarations
            if any(w in lower for w in ("koi vaccine nahi", "vaccine nahi", "no vaccine", "tika nahi", "koi injection nahi", "vaccine na", "vaccine n/a", "vaccine not applicable")):
                session_na_fields.add("vaccinations")
                if current_record:
                    current_record.vaccinations_given = ["None"]

            if any(w in lower for w in ("appointment nahi", "no appointment", "agla appointment nahi", "next visit nahi", "appointment na", "appointment n/a", "tareekh nahi", "appointment not applicable")):
                session_na_fields.add("next_visit_date")
                if current_record:
                    current_record.next_visit_date = None
                    tasks = list(current_record.follow_up_tasks or [])
                    if "Next visit: Not Applicable" not in tasks:
                        tasks.append("Next visit: Not Applicable")
                    current_record.follow_up_tasks = tasks

            if any(w in lower for w in ("vajan nahi", "weight nahi", "no weight", "scale nahi", "weight na", "weight n/a", "weight not applicable", "vajan nahi liya")):
                session_na_fields.add("weight_kg")
                if current_record:
                    current_record.weight_kg = None

            # 3. Check for save / confirmation intent
            is_save_request = current_record and any(
                kw in lower for kw in (
                    "confirm", "theek hai, save", "theek hai save", "save karo", "save karde",
                    "save kar do", "save kar dijiye", "record save", "haan save", "haan theek hai, save"
                )
            )
            if not is_save_request and current_record and any(kw == lower or f" {kw}" in lower for kw in ("theek hai", "sahi hai", "haan theek hai")):
                # Conversational agreement treated as save request if user already heard readback
                is_save_request = True

            if is_save_request and current_record:
                # ── Guarded Confirmation Gate: Refuse save if essential fields missing & not N/A ──
                missing = visit_extractor.detect_missing_fields(current_record, na_fields=session_na_fields)
                if missing:
                    logger.info("Save blocked: mandatory fields missing %s", missing)
                    await websocket.send_text(
                        _ws_event(
                            "save_blocked",
                            {
                                "record": current_record.model_dump(mode="json"),
                                "missing_fields": missing,
                            },
                        )
                    )
                    notice_speech = await readback_generator.generate_save_blocked_notice(language, missing)
                    await websocket.send_text(_ws_event("agent_speaking", {"speaking": True, "text": notice_speech}))
                    try:
                        async for chunk in pipeline.stream_speech(notice_speech):
                            await websocket.send_bytes(chunk)
                    except Exception as e:
                        logger.debug("Save-blocked speech error: %s", e)
                    finally:
                        await websocket.send_text(_ws_event("agent_speaking", {"speaking": False, "text": ""}))
                    return

                # All required fields present or marked N/A: Proceed with save
                current_record.confirmed = True
                try:
                    saved_id = await db.save_record(current_record)
                    await websocket.send_text(
                        _ws_event(
                            "record_confirmed",
                            {"record": current_record.model_dump(mode="json"), "saved_id": saved_id},
                        )
                    )
                    confirm_speech = "Record safaltapoorvak save ho gaya hai."
                    if language.startswith("kn"):
                        confirm_speech = "ದಾಖಲೆಯನ್ನು ಯಶಸ್ವಿಯಾಗಿ ಉಳಿಸಲಾಗಿದೆ."
                    elif language.startswith("ta"):
                        confirm_speech = "பதிவு வெற்றிகரமாக சேமிக்கப்பட்டது."
                    elif language.startswith("te"):
                        confirm_speech = "రికార్డు విజయవంతంగా సేవ్ చేయబడింది."
                    elif language.startswith("mr"):
                        confirm_speech = "नोंद यशस्वीरित्या सेव्ह केली गेली आहे."
                    await websocket.send_text(_ws_event("agent_speaking", {"speaking": True, "text": confirm_speech}))
                    try:
                        async for chunk in pipeline.stream_speech(confirm_speech):
                            await websocket.send_bytes(chunk)
                    except Exception as e:
                        logger.debug("Confirm speech stream error: %s", e)
                    finally:
                        await websocket.send_text(_ws_event("agent_speaking", {"speaking": False, "text": ""}))
                except Exception as e:
                    logger.error("Failed to save confirmed record: %s", e)
                    await websocket.send_text(
                        _ws_event("error", {"code": "SAVE_FAILED", "message": str(e)})
                    )
                return

            # 4. Check if this is a correction intent for an existing record
            is_correction = current_record is not None and any(
                kw in lower for kw in ("nahi", "galat", "no", "change", "badal", "update", "correction")
            )

            danger_signs = []
            danger_source = "deterministic"

            if is_correction and current_record:
                updated = await visit_extractor.apply_correction(current_record, text)
                if updated:
                    current_record = updated
                    current_missing_fields = visit_extractor.detect_missing_fields(current_record, na_fields=session_na_fields)
            else:
                ext_res = await visit_extractor.extract(text, active_lang)
                record, danger_signs, danger_source = ext_res
                if hasattr(ext_res, "na_fields") and ext_res.na_fields:
                    session_na_fields.update(ext_res.na_fields)

                current_missing_fields = getattr(ext_res, "missing_fields", None) or (
                    visit_extractor.detect_missing_fields(record, na_fields=session_na_fields) if record else []
                )
                detected_lang = getattr(ext_res, "detected_language", None) or active_lang

                # Auto-detect language transition
                if detected_lang and detected_lang != language:
                    logger.info("Language auto-detected: %s (%s)", detected_lang, get_language_label(detected_lang))
                    language = detected_lang
                    await pipeline.change_language(detected_lang)
                    await websocket.send_text(
                        _ws_event(
                            "language_detected",
                            {
                                "language": detected_lang,
                                "label": get_language_label(detected_lang),
                            },
                        )
                    )

                if record:
                    # Preserve existing patient context if follow-up turn in same session
                    if current_record:
                        if not record.beneficiary_name or record.beneficiary_name == "Priya Devi":
                            record.beneficiary_id = current_record.beneficiary_id
                            record.beneficiary_name = current_record.beneficiary_name
                        if current_record.weight_kg and not any(kw in lower for kw in ("weight", "kilo", "kg")):
                            record.weight_kg = current_record.weight_kg
                        if current_record.vaccinations_given and not record.vaccinations_given:
                            record.vaccinations_given = current_record.vaccinations_given
                    current_record = record
                    current_missing_fields = visit_extractor.detect_missing_fields(current_record, na_fields=session_na_fields)

            if current_record:
                # ── CRITICAL CLINICAL DANGER INVARIANT ──
                # If danger signs detected, prompt ONLY immediate referral!
                # All missing administrative field nagging is STRICTLY muted!
                if current_record.danger_flag or danger_signs:
                    referral_msg = current_record.referral_action or danger_detector.get_referral_message(language)
                    active_signs = current_record.danger_signs_detected or [s["id"] for s in danger_signs]
                    active_labels = [s.get("label", s.get("id")) for s in danger_signs] if danger_signs else active_signs

                    await websocket.send_text(
                        _ws_event(
                            "danger_alert",
                            {
                                "signs": active_signs,
                                "labels": active_labels,
                                "message": referral_msg,
                                "source": danger_source,
                            },
                        )
                    )
                    # Emit draft showing danger flag, with missing fields suppressed
                    await websocket.send_text(
                        _ws_event(
                            "record_draft",
                            {
                                "record": current_record.model_dump(mode="json"),
                                "missing_fields": [],
                            },
                        )
                    )
                    # Spoken PHC referral instruction ONLY
                    await websocket.send_text(_ws_event("agent_speaking", {"speaking": True, "text": referral_msg}))
                    try:
                        async for chunk in pipeline.stream_speech(referral_msg):
                            await websocket.send_bytes(chunk)
                    except Exception as e:
                        logger.debug("Referral speech stream error: %s", e)
                    finally:
                        await websocket.send_text(_ws_event("agent_speaking", {"speaking": False, "text": ""}))
                    # Exit turn immediately — no administrative prompts during clinical emergencies!
                    return

                # Emit draft visit record card including missing_fields list
                await websocket.send_text(
                    _ws_event(
                        "record_draft",
                        {
                            "record": current_record.model_dump(mode="json"),
                            "missing_fields": current_missing_fields,
                        },
                    )
                )

                # Avoid repetitive nagging: pick at most one unasked field to inquire about
                unasked = [f for f in current_missing_fields if f not in session_asked_fields]
                fields_to_nudge = []
                if unasked:
                    fields_to_nudge = [unasked[0]]
                    session_asked_fields.add(unasked[0])

                # Generate concise, natural readback
                readback_text = await readback_generator.generate(
                    current_record,
                    language,
                    missing_fields=fields_to_nudge,
                )
                await websocket.send_text(_ws_event("agent_speaking", {"speaking": True, "text": readback_text}))
                try:
                    async for chunk in pipeline.stream_speech(readback_text):
                        await websocket.send_bytes(chunk)
                except Exception as e:
                    logger.debug("Readback speech stream error: %s", e)
                finally:
                    await websocket.send_text(_ws_event("agent_speaking", {"speaking": False, "text": ""}))

    # ── WebSocket Main Loop ────────────────────────────────────────────────

    try:
        while True:
            data = await websocket.receive()

            if "bytes" in data and data["bytes"]:
                # ── Binary PCM audio frame (Client Mic → Server) ──
                pcm_chunk: bytes = data["bytes"]
                try:
                    await pipeline.process_pcm_chunk(pcm_chunk)
                except Exception as e:
                    logger.debug("Error processing audio chunk: %s", e)

            elif "text" in data and data["text"]:
                # ── JSON control frame (Client → Server) ──
                try:
                    event = json.loads(data["text"])
                except json.JSONDecodeError:
                    await websocket.send_text(
                        _ws_event("error", {"code": "INVALID_JSON", "message": "Malformed JSON"})
                    )
                    continue

                event_type = event.get("type", "")
                payload = event.get("payload", {})

                if event_type == "session_start":
                    language = payload.get("language", language)
                    pipeline.mode = payload.get("mode", "vad")

                elif event_type == "language_change":
                    language = payload.get("language", language)
                    await pipeline.change_language(language)
                    await websocket.send_text(
                        _ws_event(
                            "session_ready",
                            {
                                "session_id": session_id,
                                "language": language,
                                "audio_sample_rate": 16000,
                            },
                        )
                    )

                elif event_type == "barge_in":
                    # Instant cancel of active TTS audio
                    pipeline.handle_barge_in()
                    await websocket.send_text(_ws_event("barge_in_ack"))

                elif event_type == "ptt_state":
                    # Push-to-Talk button toggle
                    pipeline.set_ptt_state(payload.get("active", False))

                elif event_type == "text_turn_debug":
                    # Debug text input (simulates speech for testing)
                    text = payload.get("text", "")
                    if text:
                        await websocket.send_text(
                            _ws_event("transcript_final", {"text": text, "language": language})
                        )
                        await process_text_turn(text, language)

                elif event_type == "session_purge":
                    # DPDP Act compliance purge
                    result = await db.purge_all()
                    await websocket.send_text(
                        _ws_event(
                            "session_purged",
                            {
                                "transcripts_deleted": result["transcripts_deleted"],
                                "records_deleted": result["records_deleted"],
                            },
                        )
                    )

                else:
                    await websocket.send_text(
                        _ws_event(
                            "error",
                            {"code": "UNKNOWN_EVENT", "message": f"Unknown event type: {event_type}"},
                        )
                    )

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: %s", session_id)
    except Exception as e:
        logger.error("Error in WebSocket session %s: %s", session_id, e)
    finally:
        await pipeline.shutdown()
