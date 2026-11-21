"""
SwasthyaVaani — Seed Synthetic Beneficiaries into SQLite
Usage: python -m scripts.seed_db
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path


async def main() -> None:
    from backend.db import db

    # Load synthetic beneficiaries
    data_path = Path(__file__).resolve().parent.parent / "data" / "synthetic_beneficiaries.json"
    with open(data_path, encoding="utf-8") as f:
        beneficiaries = json.load(f)

    # Initialize DB and seed
    await db.init_db()
    count = await db.seed_beneficiaries(beneficiaries)
    await db.close()

    print(f"✅ Seeded {count} synthetic beneficiaries into {db.db_path}")


if __name__ == "__main__":
    asyncio.run(main())
