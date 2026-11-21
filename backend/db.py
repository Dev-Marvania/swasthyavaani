"""
SwasthyaVaani — Async SQLite Database with Fernet Encryption at Rest
Stores visit records and transcripts (DPDP-compliant encrypted storage).
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import aiosqlite

from backend.config import settings
from backend.crypto import CryptoManager
from backend.models import ASHAVisitRecord


class DatabaseManager:
    """Async SQLite database with Fernet encryption at rest."""

    def __init__(self) -> None:
        self.db_path = settings.sqlite_db_path
        self._crypto: CryptoManager | None = None
        self._db: aiosqlite.Connection | None = None

    @property
    def crypto(self) -> CryptoManager:
        if self._crypto is None:
            if not settings.encryption_key:
                raise RuntimeError(
                    "ENCRYPTION_KEY is not set. "
                    "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
                )
            self._crypto = CryptoManager(settings.encryption_key)
        return self._crypto

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def init_db(self) -> None:
        """Create tables if they don't exist with WAL mode for concurrency."""
        self._db = await aiosqlite.connect(self.db_path, timeout=30.0)
        try:
            await self._db.execute("PRAGMA journal_mode=WAL;")
        except Exception:
            pass
        try:
            await self._db.execute("PRAGMA busy_timeout=30000;")
        except Exception:
            pass
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS visit_records (
                record_id   TEXT PRIMARY KEY,
                data        TEXT NOT NULL,
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS transcripts (
                transcript_id TEXT PRIMARY KEY,
                session_id    TEXT NOT NULL,
                data          TEXT NOT NULL,
                created_at    TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS beneficiaries (
                beneficiary_id TEXT PRIMARY KEY,
                data           TEXT NOT NULL
            )
        """)
        await self._db.commit()

    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    # ── Visit Records ──────────────────────────────────────────────────

    async def save_record(self, record: ASHAVisitRecord) -> str:
        """Save a confirmed visit record (encrypted). Returns the record_id."""
        assert self._db is not None, "Database not initialized. Call init_db() first."
        record_id = record.record_id or f"REC-{uuid.uuid4().hex[:8].upper()}"
        record.record_id = record_id
        encrypted_data = self.crypto.encrypt_json(record.model_dump(mode="json"))
        await self._db.execute(
            "INSERT OR REPLACE INTO visit_records (record_id, data) VALUES (?, ?)",
            (record_id, encrypted_data),
        )
        await self._db.commit()
        return record_id

    async def get_records(self) -> list[ASHAVisitRecord]:
        """Retrieve and decrypt all visit records."""
        assert self._db is not None, "Database not initialized. Call init_db() first."
        cursor = await self._db.execute("SELECT data FROM visit_records ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        records: list[ASHAVisitRecord] = []
        for (encrypted_data,) in rows:
            data = self.crypto.decrypt_json(encrypted_data)
            records.append(ASHAVisitRecord(**data))
        return records

    # ── Transcripts ────────────────────────────────────────────────────

    async def save_transcript(self, session_id: str, transcript: str) -> str:
        """Save a session transcript (encrypted)."""
        assert self._db is not None
        transcript_id = f"TXN-{uuid.uuid4().hex[:8].upper()}"
        encrypted_data = self.crypto.encrypt(transcript)
        await self._db.execute(
            "INSERT INTO transcripts (transcript_id, session_id, data) VALUES (?, ?, ?)",
            (transcript_id, session_id, encrypted_data),
        )
        await self._db.commit()
        return transcript_id

    # ── Beneficiaries ──────────────────────────────────────────────────

    async def get_beneficiaries(self) -> list[dict[str, Any]]:
        """Retrieve all synthetic beneficiaries."""
        assert self._db is not None
        cursor = await self._db.execute("SELECT data FROM beneficiaries")
        rows = await cursor.fetchall()
        return [json.loads(row[0]) for row in rows]

    async def seed_beneficiaries(self, beneficiaries: list[dict[str, Any]]) -> int:
        """Seed synthetic beneficiary data. Returns count inserted."""
        assert self._db is not None
        count = 0
        for b in beneficiaries:
            await self._db.execute(
                "INSERT OR REPLACE INTO beneficiaries (beneficiary_id, data) VALUES (?, ?)",
                (b["beneficiary_id"], json.dumps(b, ensure_ascii=False)),
            )
            count += 1
        await self._db.commit()
        return count

    # ── DPDP Purge ─────────────────────────────────────────────────────

    async def purge_all(self) -> dict[str, int]:
        """Delete ALL records and transcripts. For post-judging DPDP compliance."""
        assert self._db is not None
        rec_cursor = await self._db.execute("SELECT COUNT(*) FROM visit_records")
        rec_count = (await rec_cursor.fetchone())[0]
        txn_cursor = await self._db.execute("SELECT COUNT(*) FROM transcripts")
        txn_count = (await txn_cursor.fetchone())[0]

        await self._db.execute("DELETE FROM visit_records")
        await self._db.execute("DELETE FROM transcripts")
        await self._db.commit()

        return {"records_deleted": rec_count, "transcripts_deleted": txn_count}


# Singleton — import this wherever you need database access
db = DatabaseManager()
