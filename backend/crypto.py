"""
SwasthyaVaani — Fernet Encryption Helpers (DPDP Compliance)
Encrypts/decrypts record and transcript data at rest.
"""

from __future__ import annotations

import json
from typing import Any

from cryptography.fernet import Fernet


class CryptoManager:
    """Thin wrapper around Fernet for encrypting data at rest."""

    def __init__(self, key: str | bytes) -> None:
        if isinstance(key, str):
            key = key.encode("utf-8")
        self.fernet = Fernet(key)

    # ── String helpers ─────────────────────────────────────────────────

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a UTF-8 string → URL-safe base64 token string."""
        return self.fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, token: str) -> str:
        """Decrypt a token string → original UTF-8 string."""
        return self.fernet.decrypt(token.encode("utf-8")).decode("utf-8")

    # ── JSON helpers ───────────────────────────────────────────────────

    def encrypt_json(self, data: Any) -> str:
        """Serialize *data* to JSON then encrypt."""
        return self.encrypt(json.dumps(data, ensure_ascii=False))

    def decrypt_json(self, token: str) -> Any:
        """Decrypt *token* then deserialize from JSON."""
        return json.loads(self.decrypt(token))

    # ── Key generation utility ─────────────────────────────────────────

    @staticmethod
    def generate_key() -> str:
        """Generate a new Fernet key (use once, store in .env)."""
        return Fernet.generate_key().decode("utf-8")
