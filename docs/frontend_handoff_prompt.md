# Frontend Handoff Prompt (Lovable / Google AI Studio)

Paste this prompt into Lovable or Google AI Studio so Teammate 3's UI matches our backend contracts directly:

```text
Build a mobile-first web app (optimized for low-end Android phones) called "SwasthyaVaani" — a zero-typing voice field register for Indian ASHA community health workers.

### Backend Connection (Configurable via Settings Gear)
- Allow configuring `BACKEND_HTTP_URL` (e.g., https://xxxx.trycloudflare.com) and `BACKEND_WS_URL` (e.g., wss://xxxx.trycloudflare.com) in a header settings drawer.
- Include header `"ngrok-skip-browser-warning": "true"` on REST calls.
- WebSocket: `${BACKEND_WS_URL}/ws/voice?lang=${selectedLang}`
- REST: `GET /api/beneficiaries`, `GET /api/records`, `DELETE /api/admin/purge`

### Audio Streaming
- Mic capture: `{ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 } }`.
- Downsample mic audio to 16 kHz 16-bit mono PCM (`Int16Array`) using an inline Blob-loaded AudioWorklet and send raw binary ArrayBuffers over the WebSocket.
- Play incoming binary 16 kHz mono PCM TTS chunks sequentially via Web Audio API, flushing immediately on `barge_in` / `barge_in_ack`.
- Include both continuous hands-free mode (with an Interrupt / Barge-In button) and a Push-to-Talk fallback toggle (`ptt_state`).

### JSON Events & Schema
Follow `contracts/ws_protocol.md` and `contracts/visit_record.schema.json`:
- 1-Tap Language bar: हिन्दी (`hi-IN`), ಕನ್ನಡ (`kn-IN`), தமிழ் (`ta-IN`), తెలుగు (`te-IN`), मराठी (`mr-IN`).
- Prominent RED urgent PHC referral banner whenever `danger_alert` arrives or `record.danger_flag === true`.
- Live Structured Visit Record card + Saved Visits tab + collapsible mock text input (`text_turn_debug`) + Footer with "Synthetic Data Only • Encrypted at Rest (DPDP)" and red "Purge Demo Data" button.
```
