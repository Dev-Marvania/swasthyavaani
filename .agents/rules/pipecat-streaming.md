---
trigger: always_on
---
# Pipecat Streaming & Latency Engineering Rules

1. **Streaming End-to-End:** Stream 16 kHz, 16-bit signed little-endian mono PCM chunks directly into Gnani Prisma v3.0 STT and stream sentence chunks into Gnani Timbre v3.0 TTS to minimize Time to First Audio.
2. **Barge-In & Endpointing:** Enable `allow_interruptions=True` in Pipecat and handle `barge_in` control events by cancelling active TTS output immediately and returning `barge_in_ack`.
3. **Noise Resilience:** Tune Silero VAD for street/household background noise and support `ptt_state` gating when Push-to-Talk fallback is active.
4. **Concise Spoken Read-Back:** Keep read-back confirmations to 1-2 short sentences so an ASHA worker can confirm or correct by voice while walking between houses.
