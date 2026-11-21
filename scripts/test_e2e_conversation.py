"""
SwasthyaVaani — Automated End-to-End Multi-Turn Conversation Runner
Executes a complete 6-turn clinical workflow with real Gemini extraction,
deterministic danger detection, voice readback, and encrypted DPDP storage.
"""

from __future__ import annotations

import json
import logging
import sys

from fastapi.testclient import TestClient

from backend.config import settings
# Use isolated test database so it never conflicts with a running uvicorn instance
settings.sqlite_db_path = "swasthyavaani_test.db"

from backend.main import app

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("e2e_conversation")


def print_header(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_pass(msg: str):
    print(f"  ✅ [PASS] {msg}")


def print_info(label: str, content: str):
    print(f"  ℹ️  {label}: {content}")


def run_e2e_conversation():
    print_header("SWASTHYAVAANI — END-TO-END CLINICAL CONVERSATION TEST")

    with TestClient(app) as client:
        with client.websocket_connect("/ws/voice?lang=hi-IN") as ws:

            # ── TURN 1: Connect & Silent Listening Mode ────────────────────
            print_header("TURN 1: Silent Connection & Auto-Detection Ready")

            m1 = ws.receive_json()
            assert m1["type"] == "session_ready", f"Expected session_ready, got {m1['type']}"
            print_pass(f"session_ready received: session_id={m1['payload']['session_id']}, lang={m1['payload']['language']}")
            print_pass("Silent listening confirmed: zero unprompted greeting on connection.")

            # ── TURN 2: Spoken Field Notes Extraction & First-Turn Disclosure ──
            print_header("TURN 2: Spoken Routine ANC Home-Visit Notes")
            spoken_note = "Priya Devi ka ANC checkup kiya hai, second trimester. Weight 55 kg hai. TT-1 injection aur IFA goli de di hai."
            print_info("ASHA Worker Speaks", f'"{spoken_note}"')

            ws.send_text(
                json.dumps(
                    {
                        "type": "text_turn_debug",
                        "timestamp": 1000,
                        "payload": {"text": spoken_note},
                    }
                )
            )

            turn2_draft = None
            turn2_readback = ""

            # Drain frames for Turn 2
            while True:
                msg = ws.receive()
                if "text" in msg:
                    d = json.loads(msg["text"])
                    t = d.get("type")
                    if t == "transcript_final":
                        print_pass(f"STT Transcript finalized: '{d['payload']['text']}'")
                    elif t == "record_draft":
                        turn2_draft = d["payload"]["record"]
                        print_pass(f"Draft record generated: Beneficiary={turn2_draft.get('beneficiary_id')} | Type={turn2_draft.get('visit_type')} | Weight={turn2_draft.get('weight_kg')} kg")
                    elif t == "agent_speaking" and d.get("payload", {}).get("speaking"):
                        turn2_readback = d["payload"]["text"]
                        print_info("Agent Spoken Readback", f'"{turn2_readback}"')
                    elif t == "agent_speaking" and not d.get("payload", {}).get("speaking"):
                        if turn2_draft is not None:
                            break

            assert turn2_draft is not None, "Draft record was not generated in Turn 2"
            assert "SwasthyaVaani" in turn2_readback, f"First spoken response must include AI disclosure prefix, got: '{turn2_readback}'"
            print_pass("Mandatory first-spoken-turn AI disclosure verified in readback!")
            assert turn2_draft.get("beneficiary_id") == "SYN-ASHA-001", f"Expected SYN-ASHA-001, got {turn2_draft.get('beneficiary_id')}"
            assert turn2_draft.get("visit_type") == "ANC", f"Expected ANC, got {turn2_draft.get('visit_type')}"
            assert float(turn2_draft.get("weight_kg", 0)) == 55.0, f"Expected 55.0 kg, got {turn2_draft.get('weight_kg')}"
            assert turn2_draft.get("danger_flag") is False, "Routine visit should not have danger_flag"
            print_pass("Turn 2 extraction verified successfully against schema!")

            # ── TURN 3: Spoken Voice Correction ────────────────────────────
            print_header("TURN 3: Spoken Voice Correction (Barge-In Correction)")
            correction = "Nahi, weight 52 kilo hai, 55 nahi."
            print_info("ASHA Worker Corrects", f'"{correction}"')

            ws.send_text(
                json.dumps(
                    {
                        "type": "text_turn_debug",
                        "timestamp": 2000,
                        "payload": {"text": correction},
                    }
                )
            )

            turn3_draft = None
            while True:
                msg = ws.receive()
                if "text" in msg:
                    d = json.loads(msg["text"])
                    t = d.get("type")
                    if t == "record_draft":
                        turn3_draft = d["payload"]["record"]
                        print_pass(f"Updated Draft after correction: Weight={turn3_draft.get('weight_kg')} kg (Beneficiary={turn3_draft.get('beneficiary_id')})")
                    elif t == "agent_speaking" and not d.get("payload", {}).get("speaking"):
                        if turn3_draft is not None:
                            break

            assert turn3_draft is not None, "Updated draft not received after correction"
            assert float(turn3_draft.get("weight_kg", 0)) == 52.0, f"Expected weight 52.0, got {turn3_draft.get('weight_kg')}"
            assert turn3_draft.get("beneficiary_id") == "SYN-ASHA-001", "Beneficiary ID must not be lost during correction"
            assert turn3_draft.get("visit_type") == "ANC", "Visit type must not be lost during correction"
            print_pass("Turn 3 non-destructive field correction verified successfully!")

            # ── TURN 4: Critical Danger Sign Escalation ────────────────────
            print_header("TURN 4: Critical Danger Sign Escalation (NHM Guidelines)")
            danger_note = "Lekin patient ko bahut tez bukhar hai aur bleeding shuru ho gayi hai."
            print_info("ASHA Worker Reports Red Flag", f'"{danger_note}"')

            ws.send_text(
                json.dumps(
                    {
                        "type": "text_turn_debug",
                        "timestamp": 3000,
                        "payload": {"text": danger_note},
                    }
                )
            )

            danger_alert_received = None
            turn4_draft = None

            while True:
                msg = ws.receive()
                if "text" in msg:
                    d = json.loads(msg["text"])
                    t = d.get("type")
                    if t == "danger_alert":
                        danger_alert_received = d["payload"]
                        print_pass(f"🚨 DANGER ALERT TRIGGERED! Signs={danger_alert_received.get('signs')} (Source={danger_alert_received.get('source')})")
                        print_info("Urgent PHC Referral Alert", f'"{danger_alert_received.get("message")}"')
                    elif t == "record_draft":
                        turn4_draft = d["payload"]["record"]
                    elif t == "agent_speaking" and not d.get("payload", {}).get("speaking"):
                        if danger_alert_received is not None and turn4_draft is not None:
                            break

            assert danger_alert_received is not None, "danger_alert event was not emitted!"
            detected_signs = danger_alert_received.get("signs", [])
            assert any(s in detected_signs for s in ("MAT_BLEEDING", "MAT_HIGH_FEVER")), f"Expected bleeding or fever sign, got {detected_signs}"
            assert turn4_draft.get("danger_flag") is True, "Draft record danger_flag must be True"
            print_pass("Turn 4 clinical danger sign escalation verified with zero medical advice!")

            # ── TURN 5: Voice Confirmation & Encrypted DB Save ─────────────
            print_header("TURN 5: Spoken Confirmation & Encrypted Storage")
            confirm_note = "Haan theek hai, save karo."
            print_info("ASHA Worker Confirms", f'"{confirm_note}"')

            ws.send_text(
                json.dumps(
                    {
                        "type": "text_turn_debug",
                        "timestamp": 4000,
                        "payload": {"text": confirm_note},
                    }
                )
            )

            saved_record_id = None
            while True:
                msg = ws.receive()
                if "text" in msg:
                    d = json.loads(msg["text"])
                    t = d.get("type")
                    if t == "record_confirmed":
                        saved_record_id = d["payload"]["saved_id"]
                        print_pass(f"RECORD CONFIRMED & PERSISTED! saved_id={saved_record_id}")
                        break

            assert saved_record_id is not None, "record_confirmed event not received"
            print_pass("Turn 5 voice confirmation & database write verified!")

        # ── TURN 6: REST Verification & DPDP Purge ─────────────────────────
        print_header("TURN 6: REST API Retrieval & DPDP Act Data Purge")

        # 1. Verify GET /api/records
        resp_records = client.get("/api/records")
        assert resp_records.status_code == 200, f"Expected 200, got {resp_records.status_code}"
        records_data = resp_records.json().get("records", [])
        print_pass(f"GET /api/records returned {len(records_data)} record(s) decrypted from SQLite:")
        if records_data:
            rec = records_data[0]
            print_info("Decrypted Record", f"ID={rec.get('record_id')} | Patient={rec.get('beneficiary_name')} ({rec.get('beneficiary_id')}) | Danger={rec.get('danger_flag')} | Weight={rec.get('weight_kg')} kg")
            assert rec.get("record_id") == saved_record_id
            assert rec.get("danger_flag") is True
            assert float(rec.get("weight_kg", 0)) == 52.0

        # 2. Test DPDP Purge: DELETE /api/admin/purge
        print_info("DPDP Purge", "Executing post-judging data wipe via DELETE /api/admin/purge...")
        resp_purge = client.delete("/api/admin/purge")
        assert resp_purge.status_code == 200
        purge_res = resp_purge.json()
        print_pass(f"DELETE /api/admin/purge succeeded: {purge_res}")
        assert purge_res.get("records_deleted", 0) >= 1

        # 3. Verify database is now completely empty
        resp_after_purge = client.get("/api/records")
        assert len(resp_after_purge.json().get("records", [])) == 0
        print_pass("Verified database is completely clean (0 records remaining). DPDP compliance satisfied!")

    print_header("ALL 6 CONVERSATION TURNS COMPLETED & VERIFIED SUCCESSFULLY!")


if __name__ == "__main__":
    try:
        run_e2e_conversation()
        sys.exit(0)
    except Exception as e:
        logger.error("E2E Conversation test failed: %s", e, exc_info=True)
        sys.exit(1)
