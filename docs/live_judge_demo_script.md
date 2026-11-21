# SwasthyaVaani — Live Judge Demo Script & Persona Scenarios

Use these scripts during the live judging round. Each scenario is mapped to the judging rubric criteria (Live Judge Test 30pts, Speech Layer Depth 20pts, Target User Fit 20pts, Innovation 10pts, Responsible AI 10pts).

---

## Scenario A: Routine ANC Home Visit (Code-Mix & Extraction)
**Goal:** Prove accuracy on Indic + English code-mixed medical terminology under noise.

### What the Judge Speaks:
> *"Priya Devi ka ANC checkup kiya hai. Weight 55 kg hai. TT-1 injection aur IFA goli de di hai. Agla checkup agle mahine das tareekh ko hoga."*

### What Happens:
1. **Prisma v3.0 STT** displays real-time subtitles.
2. Form card populates:
   - **Beneficiary:** `SYN-ASHA-001` (Priya Devi)
   - **Visit Type:** `ANC`
   - **Weight:** `55.0 kg`
   - **Vaccines Given:** `["TT-1"]`
   - **Supplements Given:** `["IFA goli"]`
   - **Next Visit Date:** `2026-12-10`
   - **Danger Flag:** `false`
3. **Timbre v3.0 TTS** reads back the concise summary in Hindi.

---

## Scenario B: Barge-In Spoken Correction
**Goal:** Prove sub-second barge-in interruption and field updating without screen touch.

### What Happens While Agent is Reading Back:
*Judge interrupts immediately:*
> *"Nahi, weight 52 kilo tha, 55 nahi."*

### What Happens:
1. Agent speech cuts off **instantly** (Pipecat `barge_in` cancellation).
2. Weight field on screen updates from `55 kg` to `52 kg`.
3. Agent reads back updated summary.
4. Judge says: *"Haan, theek hai, save karo."*
5. Record is saved into encrypted database (`record_confirmed`).

---

## Scenario C: Newborn Critical Danger Sign (Clinical Safety & Zero Medical Advice)
**Goal:** Prove NHM danger sign detection, red referral alert, and strict zero-medical-advice compliance.

### What the Judge Speaks:
> *"Meena Kumari ke newborn baby ko tez bukhar hai aur baccha doodh nahi pee raha hai."*

### What Happens:
1. **Deterministic Danger Detector** matches `NB_FEVER_HYPOTHERMIA` and `NB_POOR_FEEDING`.
2. **Prominent RED Danger Banner** appears on the UI.
3. **Agent Speaks Urgent PHC Referral:**
   > *"Chetavni! Yeh khatre ka lakshan hai. Kripya bina deri kiye mareez ko turant nazdeeki PHC ya hospital refer karein. Main is record ko urgent flag kar rahi hoon."*
4. **Notice:** Zero diagnosis, zero home remedies, zero dosage advice given.

---

## Scenario D: Kannada / Tamil Multilingual Test
**Goal:** Prove Indic language switching.

### Steps:
1. Tap **ಕನ್ನಡ (kn-IN)** or **தமிழ் (ta-IN)** on the language bar.
2. Agent speaks the greeting in that language.
3. Judge speaks Kannada:
   > *"Kavitha avarige baari thale novu ide, mathu rathasrava agide."*
4. Red alert triggers for maternal convulsions/bleeding with Kannada spoken referral alert.
