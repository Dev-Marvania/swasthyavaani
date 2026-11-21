---
trigger: always_on
---
# Responsible AI & Compliance Guardrails (Hard Invariants)

Breaking any rule below caps the Responsible AI score at 0 during live judging. Enforce these in every feature built:

1. **Mandatory First-Turn AI Disclosure:** The agent's first spoken turn MUST state that it is an AI assistant, in the user's active language (source texts from `contracts/languages.json`).
2. **Zero Medical Advice:** NEVER generate diagnoses, treatments, home remedies, or medication dosages. On any danger sign, strictly instruct immediate PHC referral in the user's language and set `danger_flag = true`.
3. **Zero Missed Danger Signs (Double Penalty Rule):** Always combine a deterministic multilingual/code-mix matcher (using `contracts/danger_signs.json`) with the LLM safety check. Never allow the LLM to suppress a deterministic danger-sign match.
4. **Synthetic Data & DPDP Act:** Use synthetic beneficiaries only (`SYN-ASHA-*`). Encrypt all stored transcripts and visit records at rest (Fernet), and provide a post-judging purge endpoint (`DELETE /api/admin/purge`) and CLI script.
5. **Secrets Security:** Never hardcode API keys or encryption keys. Load exclusively from `.env` and keep `.env` in `.gitignore`.
6. **No Voice Cloning:** Use stock Gnani Timbre v3.0 voices only.
