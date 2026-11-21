# Project: SwasthyaVaani — Voice Field Register for ASHA Workers
**Hackathon:** Gnani Voice Hackathon (Track 1: PS1 Healthcare)

## Mission
Build a real-time streaming voice backend that turns an ASHA worker's spoken home-visit notes (Indic languages + English code-mix, under household and street noise) into a structured visit record and follow-up action list with zero typing, voice read-back/correction, and immediate PHC danger-sign escalation.

## Core Stack & Constraints
- **Transport:** WebSocket streaming only (`/ws/voice`). No telephony, no phone numbers.
- **STT (Required):** Gnani Prisma v3.0 (WebSocket streaming) via Pipecat.
- **TTS (Required):** Gnani Timbre v3.0 (WebSocket streaming) via Pipecat. Standard voices only (no voice cloning).
- **Orchestration:** Pipecat (`pipecat-ai`) custom streaming pipeline (no hosted end-to-end agent platform as the core loop).
- **LLM:** Async wrapper in `agent/` defaulting to Groq (`llama-3.3-70b-versatile`) for minimum Time to First Audio (TTFA).
- **Database:** Local SQLite with Fernet encryption at rest + post-judging DPDP purge support.
- **Frontend:** Built externally by Teammate 3 in Lovable / Google AI Studio against `contracts/ws_protocol.md` and `contracts/visit_record.schema.json`.

## Team Ownership (2-Backend + External Frontend)
- **Zone A — Speech & WebSocket Streaming:** `voice/` and `backend/routers/ws.py`
- **Zone B — Agent, Clinical Safety & Encrypted DB:** `agent/`, `backend/db.py`, `backend/crypto.py`, `backend/routers/records.py`, `data/`, and `scripts/`
- **Frozen Shared Contracts (Read-Only):** `contracts/`, `AGENTS.md`, `.agents/rules/`

## Coding Standards
- Python 3.11+, async-first (`asyncio`), strict type hints, Pydantic v2 models matching `contracts/visit_record.schema.json`.
- Always read `contracts/` before writing any code that crosses module or frontend boundaries.
