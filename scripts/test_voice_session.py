"""
SwasthyaVaani — Voice Session Test Harness & CLI Simulator
Usage:
    python -m scripts.test_voice_session --lang hi-IN --text "Priya Devi ka ANC visit, weight 55 kilo, bleeding ho rahi hai"
    python -m scripts.test_voice_session --mock-audio
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

import websockets

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_voice_session")


async def run_session(ws_url: str, lang: str, text: str | None, simulate_voice: bool):
    url = f"{ws_url}/ws/voice?lang={lang}"
    logger.info("Connecting to WebSocket: %s", url)

    try:
        async with websockets.connect(url) as ws:
            # 1. Wait for session_ready (silent listening mode per Pipecat Rule 2)
            msg1 = await ws.recv()
            if isinstance(msg1, str):
                d1 = json.loads(msg1)
                logger.info("📡 Event: %s | Payload: %s", d1.get("type"), d1.get("payload"))

            if text:
                logger.info("📝 Sending text turn debug: '%s'", text)
                await ws.send(
                    json.dumps(
                        {
                            "type": "text_turn_debug",
                            "timestamp": 1000,
                            "payload": {"text": text},
                        }
                    )
                )

                # Listen for responses
                while True:
                    try:
                        resp = await asyncio.wait_for(ws.recv(), timeout=10)
                        if isinstance(resp, str):
                            data = json.loads(resp)
                            event_type = data.get("type")
                            payload = data.get("payload", {})
                            if event_type == "danger_alert":
                                logger.warning("🚨 [DANGER ALERT DETECTED]: %s | Message: %s", payload.get("signs"), payload.get("message"))
                            elif event_type == "record_draft":
                                logger.info("📋 [RECORD DRAFT]: %s", json.dumps(payload.get("record"), indent=2, ensure_ascii=False))
                            elif event_type == "agent_speaking":
                                if payload.get("speaking"):
                                    logger.info("🔊 [AGENT SPEAKING]: %s", payload.get("text"))
                            elif event_type == "transcript_final":
                                logger.info("✍️ [TRANSCRIPT FINAL]: %s", payload.get("text"))
                            elif event_type == "record_confirmed":
                                logger.info("✅ [RECORD CONFIRMED]: saved_id=%s", payload.get("saved_id"))
                                break
                        elif isinstance(resp, bytes):
                            logger.info("🎵 Received binary PCM audio chunk: %d bytes", len(resp))
                    except asyncio.TimeoutError:
                        logger.info("Session listening complete.")
                        break

    except Exception as e:
        logger.error("Session failed: %s", e)


def main():
    parser = argparse.ArgumentParser(description="SwasthyaVaani Voice Session Simulator")
    parser.add_argument("--url", default="ws://127.0.0.1:8000", help="Backend WebSocket base URL")
    parser.add_argument("--lang", default="hi-IN", help="BCP-47 language code")
    parser.add_argument("--text", default="Priya Devi ka ANC visit, weight 55 kilo, bahut bleeding ho rahi hai", help="Spoken text to simulate")
    parser.add_argument("--mock-audio", action="store_true", help="Simulate binary audio PCM streaming")
    args = parser.parse_args()

    asyncio.run(run_session(args.url, args.lang, args.text, args.mock_audio))


if __name__ == "__main__":
    main()
