---
trigger: always_on
---
# Pipecat Streaming, Latency & Conversational Voice Rules

1. **Streaming End-to-End:** Stream 16 kHz, 16-bit signed little-endian mono PCM chunks directly into Gnani Prisma v3.0 STT and stream sentence chunks into Gnani Timbre v3.0 TTS to minimize Time to First Audio.
2. **Zero Unprompted Welcome Greetings:** The session must start silently with `session_ready`. Do NOT emit audio greetings on connection. Allow the ASHA worker to initiate speech. Mandatory AI disclosure occurs naturally on the agent's first spoken response turn.
3. **Strict Monolingual Invariant:** Speak exclusively in the single auto-detected language. NEVER repeat or translate sentences in multiple languages. NEVER output bilingual parentheticals (e.g. no "(वजन)" or "(in English)").
4. **Vapi/Retell-Style Debounced Endpointing:** Buffer consecutive STT fragments with a 1.2–1.5 second silence debounce before triggering extraction/TTS. Never interrupt the ASHA worker during mid-sentence intake pauses.
5. **Instantaneous Voice Barge-In:** Continuously monitor microphone energy. If user speech energy exceeds threshold while TTS is playing, cancel audio synthesis and playback immediately (<50ms) and acknowledge barge-in.
6. **Deterministic Clinical Keyword Assurance:** Combine LLM extraction with deterministic clinical keyword dictionaries for NHM vaccines, supplements, and visit types to guarantee that clearly spoken clinical terms are never lost.
7. **Noise Resilience:** Tune Silero VAD for street/household background noise and support `ptt_state` gating when Push-to-Talk fallback is active.
8. **Concise Spoken Read-Back:** Keep read-back confirmations to 1-2 short sentences so an ASHA worker can confirm or correct by voice while walking between houses.
