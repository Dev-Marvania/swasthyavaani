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
async def voice_websocket(websocket: WebSocket, lang: str = "hi-IN"):
    """
    Main real-time voice streaming WebSocket.

    Handles:
    - Binary frames: 16 kHz 16-bit mono PCM chunks in both directions.
    - JSON frames: Session lifecycle, live transcripts, danger alerts,
      draft records, and DPDP purges per contracts/ws_protocol.md.
    """
    await websocket.accept()

    session_id = f"SES-{uuid.uuid4().hex[:12].upper()}"
    language = lang
    lang_config = _load_language_config()
    current_record: Optional[ASHAVisitRecord] = None
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
                "language": language,
                "audio_sample_rate": 16000,
            },
        )
    )

    # ── 2. Mandatory First-Turn AI Disclosure (Compliance Rule #1) ──────────

    languages = lang_config.get("languages", {})
    greeting = ""
    if language in languages:
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
        nonlocal current_record, language
        async with lock:
            # 1. Save transcript encrypted for DPDP
            try:
                await db.save_transcript(session_id, text)
            except Exception as e:
                logger.warning("Failed to save transcript: %s", e)

            # Check if this is a confirmation intent
            lower = text.lower().strip()
            if current_record and any(kw in lower for kw in ("confirm", "theek hai", "sahi hai", "save karo", "haan")):
                current_record.confirmed = True
                try:
                    saved_id = await db.save_record(current_record)
                    await websocket.send_text(
                        _ws_event(
                            "record_confirmed",
                            {"record": current_record.model_dump(mode="json"), "saved_id": saved_id},
                        )
                    )
                except Exception as e:
                    logger.error("Failed to save confirmed record: %s", e)
                    await websocket.send_text(
                        _ws_event("error", {"code": "SAVE_FAILED", "message": str(e)})
                    )
                return

            # Check if this is a correction intent for an existing record
            is_correction = current_record is not None and any(
                kw in lower for kw in ("nahi", "galat", "no", "change", "badal", "update", "correction")
            )

            if is_correction and current_record:
                updated = await visit_extractor.apply_correction(current_record, text)
                if updated:
                    current_record = updated
            else:
                record, danger_signs, danger_source = await visit_extractor.extract(text, active_lang)
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

                    # If danger signs detected, emit danger_alert immediately
                    if current_record.danger_flag and danger_signs:
                        referral_msg = current_record.referral_action or danger_detector.get_referral_message(active_lang)
                        await websocket.send_text(
                            _ws_event(
                                "danger_alert",
                                {
                                    "signs": [s["id"] for s in danger_signs],
                                    "labels": [s["label"] for s in danger_signs],
                                    "message": referral_msg,
                                    "source": danger_source,
                                },
                            )
                        )
                        # Spoken PHC referral instruction
                        await websocket.send_text(_ws_event("agent_speaking", {"speaking": True, "text": referral_msg}))
                        try:
                            async for chunk in pipeline.stream_speech(referral_msg):
                                await websocket.send_bytes(chunk)
                        except Exception as e:
                            logger.debug("Referral speech stream error: %s", e)
                        finally:
                            await websocket.send_text(_ws_event("agent_speaking", {"speaking": False, "text": ""}))

            if current_record:
                # Emit draft visit record card
                await websocket.send_text(
                    _ws_event("record_draft", {"record": current_record.model_dump(mode="json")})
                )

                # Generate concise 1-2 sentence readback
                readback_text = await readback_generator.generate(current_record, active_lang)
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
