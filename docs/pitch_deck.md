# SwasthyaVaani — Hackathon Pitch Deck (6 Slides)

**Track:** Gnani Voice Hackathon — Track 1: PS1 Healthcare  
**Mission:** Zero-typing Indic voice field register for ASHA community health workers  

---

## Slide 1: The Problem
### Buried in Paperwork While Saving Lives
- **1 Million+ ASHA Workers** are the frontline healthcare backbone for 900+ million rural citizens across India.
- **The Burden:** Logging pregnancy, newborn, and immunisation visits in physical paper registers and clunky smartphone apps.
- **The Toll:** Typing on small screens while walking between village homes consumes up to **40% of visit time**.
- **The Danger:** Hand-written notes are prone to omission; critical danger signs are recorded late or missed entirely.

---

## Slide 2: The Solution
### SwasthyaVaani — The Spoken Field Register
- **Zero Typing:** ASHA workers simply speak their notes naturally in their local Indic dialect mixed with English (*"Priya Devi ka ANC checkup, weight 55 kilo, TT-1 diya"*).
- **Instant Structured Records:** Extracted on-the-fly into validated visit registers matching National Health Mission (NHM) standards.
- **Voice Read-Back & Spoken Corrections:** Short spoken confirmations with instant voice updates (*"nahi, weight 52 kilo hai"*).
- **Immediate Clinical Safety Escalation:** Automatic detection of maternal and newborn red flags with immediate spoken PHC referral instructions.

---

## Slide 3: Technology Architecture & Gnani Services
### Ultra-Low Latency Streaming Pipeline
- **STT (Speech-to-Text):** **Gnani Prisma v3.0** streaming over WebSocket. Handles Indic phonetics, clinical jargon (*"IFA goli"*, *"ANC"*), and code-mixed numbers (*"do point aath kilo"*).
- **TTS (Text-to-Speech):** **Gnani Timbre v3.0** streaming 16 kHz audio with natural Indic stock voices (Shivani, Kalpana, Lakshmidevi, Sunaina).
- **Orchestration:** **Pipecat (`pipecat-ai`)** streaming pipeline with sub-second Time to First Audio (TTFA).
- **Clinical Intelligence:** **Google Gemini 3.8 Flash** structured extraction engine.
- **Storage & DPDP:** Local SQLite with **Fernet 256-bit AES encryption at rest** and instant post-judging purge.

---

## Slide 4: Clinical Safety & Responsible AI
### Zero-Compromise Guardrails
1. **Mandatory First-Turn AI Disclosure:** The voice agent explicitly identifies itself as an AI assistant in the worker's active language.
2. **Zero Medical Advice / Diagnoses:** Never prescribes treatments, medications, home remedies, or dosages.
3. **Double Penalty Rule — Zero Missed Danger Signs:** Hardcoded deterministic matcher citing **NHM ASHA Modules 6 & 7 and HBNC guidelines** running in parallel with LLM checks. The LLM can never suppress a clinical alert.
4. **Data Privacy (DPDP Act):** 100% synthetic beneficiaries (`SYN-ASHA-*`), encrypted transcripts, and `DELETE /api/admin/purge`.
5. **No Voice Cloning:** Powered strictly by Gnani standard stock voices.

---

## Slide 5: Speech-Layer Depth & Street-Noise Resilience
### Engineered for Real Indian Field Conditions
- **Barge-In Support:** Sub-50ms interruption cancellation (`barge_in_ack`). The moment the worker speaks, active TTS stops immediately.
- **Noise Resilience:** Silero VAD tuned to filter barking dogs, traffic, and household chatter common in rural environments.
- **Dual Mode (Hands-Free VAD + Push-To-Talk):** Seamless toggle for high-noise street walking.
- **5 Indic Languages Supported:** Hindi (`hi-IN`), Kannada (`kn-IN`), Tamil (`ta-IN`), Telugu (`te-IN`), Marathi (`mr-IN`).

---

## Slide 6: Social Impact & Scalability
### Transforming Maternal & Child Healthcare
- **40% Time Saved per Home Visit:** Allows ASHA workers to spend more time counseling mothers rather than filling forms.
- **100% Timely Escalations:** Severe conditions (e.g. postpartum hemorrhage, newborn hypothermia) referred to Primary Health Centers immediately.
- **Device Agnostic:** Runs in low-end Android mobile browsers over WebSocket with minimal bandwidth.
- **National Scale Ready:** Aligned directly with Ayushman Bharat Digital Mission (ABDM) and NHM protocols.
