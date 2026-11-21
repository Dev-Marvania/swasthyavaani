"""
SwasthyaVaani — Streaming Voice Pipeline Orchestrator
Coordinates VAD, Gnani Prisma STT, Gnani Timbre TTS, and Barge-in.
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator, Callable, Optional

from voice.stt_service import GnaniPrismaSTT
from voice.tts_service import GnaniTimbreTTS

logger = logging.getLogger(__name__)


class SwasthyaVaaniPipeline:
    """
    Streaming voice pipeline for ASHA home-visit notes.

    Capabilities:
    - End-to-end 16 kHz 16-bit mono PCM audio streaming.
    - Live STT streaming via Gnani Prisma v3.0.
    - Live TTS streaming via Gnani Timbre v3.0 with barge-in interruption.
    - PTT (Push-To-Talk) fallback gating.
    - Dynamic language switching without dropping session.
    """

    def __init__(
        self,
        on_transcript: Optional[Callable[[str, bool, str], None]] = None,
        language: str = "hi-IN",
    ) -> None:
        self.language = language
        self.on_transcript = on_transcript
        self.stt = GnaniPrismaSTT(on_transcript=self._handle_transcript)
        self.tts = GnaniTimbreTTS()
        self.mode = "vad"  # "vad" | "ptt"
        self._ptt_active = False
        self._is_speaking = False
        self._current_tts_task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        """Start STT streaming connection."""
        await self.stt.connect(self.language)
        logger.info("Voice pipeline initialized [lang=%s]", self.language)

    async def _handle_transcript(self, text: str, is_final: bool, detected_lang: str) -> None:
        """Forward STT transcript to registered callback."""
        if self.on_transcript:
            if asyncio.iscoroutinefunction(self.on_transcript):
                await self.on_transcript(text, is_final, detected_lang)
            else:
                self.on_transcript(text, is_final, detected_lang)

    async def process_pcm_chunk(self, chunk: bytes) -> None:
        """
        Process an incoming raw 16 kHz PCM chunk from the client.
        Respects PTT gating if in PTT mode.
        """
        if self.mode == "ptt" and not self._ptt_active:
            return
        await self.stt.send_audio(chunk)

    def set_ptt_state(self, active: bool) -> None:
        """Toggle Push-To-Talk state."""
        self._ptt_active = active
        logger.debug("PTT state changed to: %s", active)

    async def change_language(self, language: str) -> None:
        """Switch language in active session."""
        self.language = language
        await self.stt.change_language(language)
        logger.info("Pipeline language changed to: %s", language)

    async def stream_speech(self, text: str) -> AsyncGenerator[bytes, None]:
        """
        Stream synthesized speech PCM chunks for the provided text.
        Tracks active speaking state for barge-in.
        """
        self._is_speaking = True
        try:
            async for pcm_chunk in self.tts.synthesize(text, language=self.language):
                if not self._is_speaking:
                    break
                yield pcm_chunk
        finally:
            self._is_speaking = False

    def handle_barge_in(self) -> None:
        """Immediately interrupt active TTS speech (barge-in)."""
        self._is_speaking = False
        self.tts.cancel()
        logger.info("Pipeline barge-in executed")

    async def shutdown(self) -> None:
        """Gracefully close STT and stop TTS."""
        self.handle_barge_in()
        await self.stt.disconnect()
        logger.info("Voice pipeline shutdown")
