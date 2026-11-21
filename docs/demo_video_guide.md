# SwasthyaVaani — 2-to-3 Minute Demo Video Storyboard & Script

**Track:** Gnani Voice Hackathon (Track 1: PS1 Healthcare)  
**Target Video Duration:** 2 minutes 30 seconds  

---

## Video Outline

| Time | Scene | Visual | Audio / Spoken Dialogue |
| :--- | :--- | :--- | :--- |
| **0:00 - 0:25** | **The Hook: The Field Problem** | Video of an ASHA worker walking in a rural village with paper registers, struggling to type on a small cracked smartphone while dogs bark in the background. | *"Every day, over one million ASHA workers walk between village homes, tracking mothers and newborns. But instead of caring for patients, they spend hours typing on small screens. Notes get delayed, and warning signs get missed."* |
| **0:25 - 0:45** | **Introducing SwasthyaVaani** | SwasthyaVaani mobile web UI opens. ASHA worker taps "Start Visit". | *"Meet SwasthyaVaani — a zero-typing voice field register powered by Gnani Prisma v3.0 STT, Gnani Timbre v3.0 TTS, and Pipecat streaming."*<br/>**Agent Speaks:** *"Namaste! Main SwasthyaVaani AI sahayak hoon. Aap apni home visit ke notes bol sakti hain..."* |
| **0:45 - 1:25** | **Scenario 1: Routine ANC Visit & Voice Correction** | Worker speaks in Hindi with English code-mix: *"Priya Devi ka ANC visit hai. Weight 55 kilo. TT-1 diya, IFA goli diya."* | Live subtitles appear in real-time. Form card auto-populates.<br/>**Agent Readback:** *"Priya Devi ka ANC visit darj hua. Weight 55 kg, TT-1 aur IFA diya gaya. Kripya confirm karein."*<br/>**ASHA Worker Interrupts (Barge-In):** *"Nahi, weight 52 kilo hai."*<br/>Agent TTS cuts off instantly, form updates weight to 52 kg! |
| **1:25 - 2:05** | **Scenario 2: Critical Danger Sign Escalation** | Worker speaks: *"Bacche ko tez bukhar hai, aur doodh nahi pee raha hai."* | **Screen turns RED!** An urgent PHC Referral banner flashes.<br/>**Agent Voice Alert:** *"Chetavni! Yeh khatre ka lakshan hai. Kripya bina deri kiye mareez ko turant nazdeeki PHC refer karein!"*<br/>**Narrator:** *"Dual-path clinical safety: NHM-backed deterministic keywords combined with Gemini guardrails. Zero medical diagnosis, strict referral only."* |
| **2:05 - 2:20** | **Scenario 3: DPDP Act Compliance & Multilingual** | Taps Kannada (`kn-IN`). Agent instantly greets in Kannada. Shows "Purge Demo Data" button in footer. | *"Fully compliant with India's DPDP Act: 100% synthetic beneficiaries, transcripts encrypted at rest, and instant one-tap post-judging purge."* |
| **2:20 - 2:30** | **Conclusion & Call to Action** | Logo, team names, architecture slide. | *"SwasthyaVaani: Turning spoken words into life-saving health records. Built with Gnani API Platform."* |

---

## Recording Tips for the Demo Video:
1. **Screen + Audio:** Use OBS Studio or Loom at 1080p.
2. **Audio Levels:** Keep microphone clear, and Web Audio speaker output audible.
3. **Simulate Background Noise:** Play low village/street noise in the background during Turn 1 to prove VAD and STT accuracy!
