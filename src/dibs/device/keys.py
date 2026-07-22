"""Per-node key generation and verification. Keys are high-entropy random
tokens; only their SHA-256 hash is stored (the plaintext is unrecoverable)."""

from __future__ import annotations

import hashlib
import secrets


def generate_key() -> str:
    return secrets.token_urlsafe(32)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def verify_key(key: str, key_hash: str) -> bool:
    return secrets.compare_digest(hash_key(key), key_hash)
