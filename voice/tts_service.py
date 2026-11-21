"""
SwasthyaVaani — Gnani Timbre v3.0 TTS Service (Pipecat & Real-Time Streaming)
WebSocket streaming Text-to-Speech synthesis for Indic languages.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import AsyncGenerator, Optional

import websockets

from backend.config import settings

logger = logging.getLogger(__name__)

# Default standard stock voices per language (no voice cloning per hackathon rules)
LANGUAGE_VOICES = {
    "hi-IN": "Shivani",
    "kn-IN": "Kalpana",
    "ta-IN": "Priyasharm",
    "te-IN": "Lakshmidevi",
    "mr-IN": "Sunaina",
    "en-IN": "Shivani",
}


class GnaniTimbreTTS:
    """
    WebSocket streaming TTS service using Gnani Timbre v3.0 on api.vachana.ai.
    Streams 16 kHz 16-bit signed mono PCM audio chunks back to caller.
    """

    def __init__(self) -> None:
        self.ws_url = settings.gnani_tts_ws_url
        self.api_key = settings.gnani_api_key
        self.access_key = settings.gnani_access_key
        self._cancelled = False

    async def synthesize(
        self,
        text: str,
        language: str = "hi-IN",
        voice: Optional[str] = None,
    ) -> AsyncGenerator[bytes, None]:
        """
        Synthesize text to 16 kHz 16-bit mono PCM stream.
        Yields raw PCM audio chunks in real-time.
        """
        self._cancelled = False
        target_voice = voice or LANGUAGE_VOICES.get(language, "Shivani")

        payload = {
            "text": text,
            "model": "timbre-v3.0",
            "voice": target_voice,
            "language": language,
            "audio_config": {
                "sample_rate": 16000,
                "encoding": "linear_pcm",
                "container": "raw",
            },
        }

        headers = {
            "X-API-Key-ID": self.api_key,
        }
        if self.access_key and self.access_key != self.api_key:
            headers["accesskey"] = self.access_key

        try:
            async with websockets.connect(
                self.ws_url,
                additional_headers=headers,
                open_timeout=5,
                ping_interval=20,
            ) as ws:
                await ws.send(json.dumps(payload))

                while not self._cancelled:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=6)
                    except asyncio.TimeoutError:
                        break

                    if isinstance(msg, str):
                        try:
                            d = json.loads(msg)
                            msg_type = d.get("type")
                            if msg_type == "audio":
                                audio_b64 = d.get("data", {}).get("audio", "")
                                if audio_b64:
                                    pcm_bytes = base64.b64decode(audio_b64)
                                    yield pcm_bytes
                            elif msg_type == "complete":
                                break
                            elif msg_type == "error":
                                logger.error("Gnani TTS error: %s", d.get("message"))
                                break
                        except json.JSONDecodeError:
                            pass
        except asyncio.CancelledError:
            logger.info("TTS synthesis cancelled (barge-in)")
        except Exception as e:
            logger.error("TTS synthesis connection error: %s", e)

    def cancel(self) -> None:
        """Cancel active synthesis immediately (barge-in)."""
        self._cancelled = True
        logger.info("Gnani Timbre TTS cancelled")
