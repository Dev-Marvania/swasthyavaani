"""
SwasthyaVaani — Gnani Prisma v3.0 STT Service (Pipecat & Real-Time Streaming)
Streams 16 kHz 16-bit PCM chunks to Gnani Prisma STT and receives live transcript events.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator, Callable, Optional

import websockets

from backend.config import settings

logger = logging.getLogger(__name__)


class GnaniPrismaSTT:
    """
    WebSocket streaming STT service using Gnani Prisma v3.0 on api.vachana.ai.
    Streams 16 kHz 16-bit signed mono PCM and emits partial/final transcripts.
    """

    def __init__(self, on_transcript: Optional[Callable[[str, bool, str], None]] = None) -> None:
        self.ws_url = settings.gnani_stt_ws_url
        self.api_key = settings.gnani_api_key
        self.access_key = settings.gnani_access_key
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._language: str = "hi-IN"
        self._on_transcript = on_transcript
        self._listen_task: Optional[asyncio.Task] = None
        self._closed = False

    @property
    def is_connected(self) -> bool:
        if self._ws is None or self._closed:
            return False
        state = getattr(self._ws, "state", None)
        if state is not None:
            try:
                from websockets.protocol import State
                return state == State.OPEN
            except Exception:
                pass
        return bool(getattr(self._ws, "open", False))

    async def connect(self, language: str = "hi-IN") -> None:
        """Connect WebSocket to Gnani Prisma v3.0 STT."""
        self._language = language
        self._closed = False

        headers = {
            "X-API-Key-ID": self.api_key,
            "language_code": language,
            "model": "prisma-v3.0",
            "partials_enabled": "true",
        }
        if self.access_key and self.access_key != self.api_key:
            headers["accesskey"] = self.access_key

        try:
            self._ws = await websockets.connect(
                self.ws_url,
                additional_headers=headers,
                ping_interval=20,
                ping_timeout=10,
                max_size=None,
            )
            logger.info("Connected to Gnani Prisma v3.0 STT [lang=%s]", language)
            self._listen_task = asyncio.create_task(self._listen_loop())
        except Exception as e:
            logger.error("Failed to connect to Gnani Prisma STT: %s", e)
            self._ws = None
            raise

    async def ensure_connected(self) -> bool:
        """Ensure STT WebSocket is connected and ready."""
        if self._closed:
            return False
        if not self.is_connected:
            try:
                logger.info("Auto-reconnecting Gnani Prisma STT [lang=%s]...", self._language)
                await self.connect(self._language)
                return True
            except Exception as e:
                logger.warning("Failed to auto-reconnect to Gnani STT: %s", e)
                return False
        return True

    async def send_audio(self, pcm_chunk: bytes) -> None:
        """Send 16 kHz 16-bit mono PCM bytes to STT, auto-reconnecting if disconnected."""
        if self._closed:
            return
        if not self.is_connected:
            ok = await self.ensure_connected()
            if not ok or not self.is_connected:
                return

        try:
            await self._ws.send(pcm_chunk)
        except Exception as e:
            logger.info("STT connection send failed (%s), auto-reconnecting...", e)
            self._ws = None
            if await self.ensure_connected() and self._ws:
                try:
                    await self._ws.send(pcm_chunk)
                except Exception:
                    pass

    async def _listen_loop(self) -> None:
        """Background receiver for STT messages."""
        if not self._ws:
            return
        try:
            async for raw_msg in self._ws:
                if isinstance(raw_msg, str):
                    try:
                        data = json.loads(raw_msg)
                        msg_type = data.get("type", "")
                        logger.debug("Gnani STT raw frame: %s", raw_msg[:200])

                        # Support both standard Prisma v3.0 format and fallback fields
                        text = (data.get("text") or data.get("transcript") or data.get("asr_result") or "").strip()
                        is_final = bool(data.get("is_final", False) or msg_type in ("final", "speech_end"))
                        detected_lang = data.get("detected_language_code", self._language)

                        if text and self._on_transcript:
                            logger.info("Gnani STT transcript [final=%s, lang=%s]: %s", is_final, detected_lang, text)
                            if asyncio.iscoroutinefunction(self._on_transcript):
                                await self._on_transcript(text, is_final, detected_lang)
                            else:
                                self._on_transcript(text, is_final, detected_lang)
                    except json.JSONDecodeError:
                        pass
        except asyncio.CancelledError:
            pass
        except websockets.ConnectionClosed:
            logger.info("Gnani Prisma STT socket closed by server (utterance finished)")
            self._ws = None
            # If not explicitly disconnected by caller, auto-reconnect so subsequent speech is captured
            if not self._closed:
                asyncio.create_task(self._reconnect_after_pause())
        except Exception as e:
            logger.error("Error in STT listen loop: %s", e)
            self._ws = None

    async def _reconnect_after_pause(self) -> None:
        """Reconnect to STT after utterance completion so the next turn is immediately captured."""
        if self._closed:
            return
        await asyncio.sleep(0.1)
        if not self._closed and not self.is_connected:
            await self.ensure_connected()

    async def change_language(self, language: str) -> None:
        """Change language mid-session by reconnecting with new language header."""
        await self.disconnect()
        await self.connect(language)

    async def disconnect(self) -> None:
        """Gracefully close STT connection."""
        self._closed = True
        if self._listen_task:
            self._listen_task.cancel()
            self._listen_task = None
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
            logger.info("Disconnected from Gnani Prisma STT")
