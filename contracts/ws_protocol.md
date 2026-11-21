# SwasthyaVaani WebSocket Streaming Protocol (FROZEN CONTRACT)

**Endpoint:** `wss://<host>/ws/voice?lang=hi-IN`

## 1. Binary Frames (Audio)
- **Client → Server:** Raw 16 kHz, 16-bit signed little-endian mono PCM (`Int16Array`), 20–40 ms chunks.
- **Server → Client:** Streaming 16 kHz, 16-bit mono PCM chunks from Gnani Timbre v3.0.

## 2. JSON Control Frames
Format: `{ "type": "<event_name>", "timestamp": <epoch_ms>, "payload": { ... } }`

### Client → Server
- `session_start`: `{ "language": "hi-IN", "mode": "vad" | "ptt" }`
- `language_change`: `{ "language": "hi-IN" | "kn-IN" | "ta-IN" | "te-IN" | "mr-IN" }`
- `ptt_state`: `{ "active": true | false }`
- `barge_in`: `{ "reason": "client_vad" | "manual_stop" }`
- `text_turn_debug`: `{ "text": "..." }`
- `session_purge`: `{}`

### Server → Client
- `session_ready`: `{ "session_id": "...", "language": "hi-IN", "audio_sample_rate": 16000 }`
- `agent_speaking`: `{ "speaking": true | false, "text": "..." }`
- `transcript_partial` / `transcript_final`: `{ "text": "...", "language": "hi-IN" }`
- `record_draft`: `{ "record": <ASHAVisitRecord> }`
- `danger_alert`: `{ "signs": [...], "labels": [...], "message": "...", "source": "deterministic" | "llm" | "both" }`
- `record_confirmed`: `{ "record": <ASHAVisitRecord>, "saved_id": "..." }`
- `barge_in_ack`: `{}`
- `session_purged`: `{ "transcripts_deleted": 0, "records_deleted": 0 }`
- `error`: `{ "code": "...", "message": "..." }`

## 3. REST Endpoints
- `GET /health`
- `GET /api/beneficiaries`
- `GET /api/languages`
- `GET /api/records`
- `DELETE /api/admin/purge`
