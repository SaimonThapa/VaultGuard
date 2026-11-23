"""Shared building blocks for the controllers: events, lockout, OTPs, sessions."""

import hmac
import math
import secrets
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.core import key_store, tokens
from app.db import utcnow
from app.errors import AppError
from app.models import Otp, RefreshToken, SecurityEvent, User
from app.services import email


def record_event(db: Session, user_id: int, event_type: str, ip: str | None) -> None:
    """Adds an audit row (never any secret). The caller commits."""
    db.add(SecurityEvent(user_id=user_id, type=event_type, ip=ip))


# --- lockout (product_backend.md §6.3) ---


def too_many_attempts(locked_until: datetime) -> AppError:
    seconds = max(1, math.ceil((locked_until - utcnow()).total_seconds()))
    return AppError(
        429,
        "too_many_attempts",
        "Too many attempts. Try again later.",
        headers={"Retry-After": str(seconds)},
    )


def is_locked(locked_until: datetime | None) -> bool:
    return locked_until is not None and locked_until > utcnow()


def lock_until() -> datetime:
    return utcnow() + timedelta(minutes=config.LOCKOUT_MINUTES)


# --- OTPs (product_backend.md §6.4) ---


def create_otp(db: Session, user: User, purpose: str) -> bool:
    """Make and email a new code. Returns False (and sends nothing) during the resend cooldown.
    A new code invalidates the previous unused one. The caller commits."""
    now = utcnow()
    latest = db.scalar(
        select(Otp)
        .where(Otp.user_id == user.id, Otp.purpose == purpose)
        .order_by(Otp.id.desc())
        .limit(1)
    )
    if latest and now - latest.created_at < timedelta(seconds=config.OTP_RESEND_SECONDS):
        return False
    for old in db.scalars(
        select(Otp).where(Otp.user_id == user.id, Otp.purpose == purpose, Otp.used_at.is_(None))
    ):
        old.used_at = now
    code = f"{secrets.randbelow(10**6):06d}"
    db.add(
        Otp(
            user_id=user.id,
            purpose=purpose,
            code_hmac=tokens.hash_otp(user.id, purpose, code),
            expires_at=now + timedelta(minutes=config.OTP_TTL_MINUTES),
        )
    )
    email.send_otp(user.email, purpose, code)
    return True


def verify_otp(
    db: Session, user: User | None, purpose: str, code: str, *, consume: bool = True
) -> Otp:
    """Raises 400 invalid_otp for every failure (wrong, expired, used, too many attempts).
    With consume=False the code stays valid; the caller sets `used_at` once the whole action
    succeeds (so a wrong recovery key doesn't burn the emailed code)."""
    fail = AppError(400, "invalid_otp", "That code didn't work.")
    if user is None:
        raise fail
    now = utcnow()
    otp = db.scalar(
        select(Otp)
        .where(
            Otp.user_id == user.id,
            Otp.purpose == purpose,
            Otp.used_at.is_(None),
            Otp.expires_at > now,
        )
        .order_by(Otp.id.desc())
        .limit(1)
    )
    if otp is None:
        raise fail
    if hmac.compare_digest(otp.code_hmac, tokens.hash_otp(user.id, purpose, code)):
        if consume:
            otp.used_at = now
        return otp
    otp.attempts += 1
    if otp.attempts >= config.OTP_MAX_ATTEMPTS:
        otp.used_at = now  # dead: the attacker must request a new code
    db.commit()
    raise fail


# --- sessions ---


def start_session(db: Session, user: User, session_id: str | None = None) -> tuple[dict, str]:
    """New refresh-token row (same session id when rotating). Returns (payload, refresh_token)."""
    session_id = session_id or tokens.new_session_id()
    refresh = tokens.new_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            session_id=session_id,
            token_hash=tokens.hash_refresh_token(refresh),
            expires_at=utcnow() + timedelta(days=config.REFRESH_TOKEN_DAYS),
        )
    )
    payload = {
        "access_token": tokens.create_access_token(user.id, session_id),
        "user": {"id": user.id, "username": user.username, "email": user.email},
        "vault": {"set_up": user.vault_set_up, "unlocked": key_store.is_unlocked(session_id)},
    }
    return payload, refresh


def revoke_session(db: Session, session_id: str) -> None:
    now = utcnow()
    for row in db.scalars(
        select(RefreshToken).where(
            RefreshToken.session_id == session_id, RefreshToken.revoked_at.is_(None)
        )
    ):
        row.revoked_at = now
    key_store.drop(session_id)


def revoke_user_sessions(db: Session, user_id: int, except_session: str | None = None) -> None:
    """Revoke every session of a user (optionally keeping one) and drop their vault keys."""
    now = utcnow()
    for row in db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
        )
    ):
        if row.session_id != except_session:
            row.revoked_at = now
    key_store.drop_user(user_id, except_session)
