"""
SwasthyaVaani — DPDP Post-Judging Data Purge Script
Usage: python -m scripts.purge_data

Deletes ALL visit records and transcripts from the encrypted SQLite database.
Required for DPDP Act compliance after hackathon judging.
"""

from __future__ import annotations

import asyncio


async def main() -> None:
    from backend.db import db

    await db.init_db()
    result = await db.purge_all()
    await db.close()

    print("🗑️  DPDP Purge Complete:")
    print(f"   Records deleted:     {result['records_deleted']}")
    print(f"   Transcripts deleted: {result['transcripts_deleted']}")


if __name__ == "__main__":
    asyncio.run(main())
