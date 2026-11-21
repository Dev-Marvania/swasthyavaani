---
trigger: always_on
---
# Collaboration & Anti-Collision Rules

1. **Confirm Your Zone Before Editing:**
   - **Zone A (Speech & Streaming):** `voice/` and `backend/routers/ws.py` ONLY.
   - **Zone B (Agent, Safety & DB):** `agent/`, `backend/db.py`, `backend/crypto.py`, `backend/routers/records.py`, `data/`, and `scripts/` ONLY.
   - Never edit or refactor files outside your assigned zone unless explicitly instructed.
2. **Keep `backend/main.py` Minimal:**
   - Once created, `backend/main.py` should ONLY configure CORS, `/health`, and mount routers (`records` and `ws`). Do not put business logic or WS handlers directly in `backend/main.py`.
3. **Freeze `contracts/`:**
   - Treat all files in `contracts/` as read-only because both backend teammates and the external Lovable / Google AI Studio frontend depend on them. Propose diffs in chat before modifying any contract.
4. **Do Not Create a Frontend Folder:**
   - The frontend is maintained externally by Teammate 3 in Lovable / Google AI Studio.
5. **Branch Discipline:**
   - Zone A works on `feat/voice-*`; Zone B works on `feat/agent-db-*`. Never commit directly to `main`.
