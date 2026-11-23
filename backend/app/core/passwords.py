"""Account password hashing (Argon2id via argon2-cffi) and the shared strength check."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from zxcvbn import zxcvbn

_hasher = PasswordHasher()  # library defaults are Argon2id with a random salt
_DUMMY_HASH = _hasher.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(stored_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    return _hasher.check_needs_rehash(stored_hash)


def dummy_verify(password: str) -> None:
    """Burn the same time as a real check so an unknown username can't be timed."""
    verify_password(_DUMMY_HASH, password)


def strength(secret: str, user_inputs: list[str] | None = None) -> tuple[int, float]:
    """Returns (zxcvbn score 0-4, guesses_log10). Long inputs are cut to keep zxcvbn fast."""
    result = zxcvbn(secret[:256], user_inputs=user_inputs or [])
    return result["score"], float(result["guesses_log10"])
