"""Access JWTs, opaque refresh tokens and OTP hashing."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import jwt

from app.config import ACCESS_TOKEN_MINUTES, JWT_SECRET, OTP_PEPPER

ALGORITHM = "HS256"


def new_session_id() -> str:
    return secrets.token_urlsafe(16)


def create_access_token(user_id: int, session_id: str) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "sid": session_id,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_MINUTES),
    }
    return jwt.encode(claims, JWT_SECRET, algorithm=ALGORITHM)


def decode_access_token(token: str) -> tuple[int, str] | None:
    """Returns (user_id, session_id), or None for any invalid token (expired, forged, alg=none)."""
    try:
        claims = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[ALGORITHM],  # pinned: blocks alg=none and key-confusion tricks
            options={"require": ["exp", "sub", "sid"]},
        )
        if claims.get("type") != "access":
            return None
        return int(claims["sub"]), str(claims["sid"])
    except (jwt.PyJWTError, ValueError):
        return None


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)  # 256 random bits


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def hash_otp(user_id: int, purpose: str, code: str) -> str:
    message = f"{user_id}:{purpose}:{code}".encode()
    return hmac.new(OTP_PEPPER.encode(), message, "sha256").hexdigest()
