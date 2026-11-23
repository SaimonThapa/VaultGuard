"""All cryptography in one pure module (no FastAPI, no DB). Built only on argon2-cffi and
`cryptography`: no home-made primitives.

Envelope encryption: a random per-user DEK encrypts entry fields (AES-256-GCM). The DEK is stored
wrapped by a key derived from the master key, and again by one derived from the recovery key.
"""

import hmac
import secrets
from dataclasses import dataclass

from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

NONCE_BYTES = 12
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
RECOVERY_SYMBOLS = 26  # 26 x 5 bits = 130 bits


class IntegrityError(Exception):
    """A GCM tag check failed: the data was tampered with, corrupted or moved."""


@dataclass(frozen=True)
class KdfParams:
    time_cost: int
    memory_kib: int
    parallelism: int


def derive_keys(secret: str, salt: bytes, params: KdfParams) -> tuple[bytes, bytes]:
    """Master/recovery key -> (kek, verifier). Argon2id, then HKDF splits two independent keys,
    so the stored verifier reveals nothing about the KEK."""
    raw = hash_secret_raw(
        secret.encode(),
        salt,
        time_cost=params.time_cost,
        memory_cost=params.memory_kib,
        parallelism=params.parallelism,
        hash_len=32,
        type=Type.ID,
    )
    kek = HKDF(hashes.SHA256(), 32, None, b"vaultguard-kek").derive(raw)
    verifier = HKDF(hashes.SHA256(), 32, None, b"vaultguard-verifier").derive(raw)
    return kek, verifier


def verifier_matches(stored: bytes, candidate: bytes) -> bool:
    return hmac.compare_digest(stored, candidate)


def encrypt(key: bytes, plaintext: str, aad: str) -> bytes:
    """AES-256-GCM with a fresh random nonce. Returns nonce | ciphertext | tag."""
    nonce = secrets.token_bytes(NONCE_BYTES)
    return nonce + AESGCM(key).encrypt(nonce, plaintext.encode(), aad.encode())


def decrypt(key: bytes, blob: bytes, aad: str) -> str:
    """Raises IntegrityError if the tag fails (wrong key, edited bytes or wrong AAD)."""
    try:
        return AESGCM(key).decrypt(blob[:NONCE_BYTES], blob[NONCE_BYTES:], aad.encode()).decode()
    except (InvalidTag, ValueError, UnicodeDecodeError) as exc:
        raise IntegrityError from exc


def field_aad(user_id: int, entry_id: str, field: str) -> str:
    """Binds a ciphertext to its user, entry and field, so it can't be moved elsewhere."""
    return f"{user_id}|{entry_id}|{field}"


def wrap_dek(kek: bytes, dek: bytes) -> bytes:
    return encrypt(kek, dek.hex(), "dek")


def unwrap_dek(kek: bytes, blob: bytes) -> bytes:
    return bytes.fromhex(decrypt(kek, blob, "dek"))


def new_dek() -> bytes:
    return secrets.token_bytes(32)


def new_salt() -> bytes:
    return secrets.token_bytes(16)


def new_recovery_key() -> str:
    """130 random bits as 26 Crockford base32 symbols: XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XX."""
    symbols = "".join(secrets.choice(CROCKFORD) for _ in range(RECOVERY_SYMBOLS))
    return "-".join(symbols[i : i + 4] for i in range(0, RECOVERY_SYMBOLS, 4))


def normalize_recovery_key(text: str) -> str | None:
    """Ignore dashes/spaces/case and Crockford look-alikes (I,L -> 1; O -> 0).
    Returns None if the result isn't a valid 26-symbol key."""
    cleaned = text.upper().replace("-", "").replace(" ", "")
    cleaned = cleaned.replace("I", "1").replace("L", "1").replace("O", "0")
    if len(cleaned) != RECOVERY_SYMBOLS or any(c not in CROCKFORD for c in cleaned):
        return None
    return cleaned
