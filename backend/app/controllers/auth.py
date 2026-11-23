"""Auth logic: sign up, verify, log in, refresh, log out, password reset (product_backend.md §5.1).

Plain functions. They get a DB session and plain values; they never see the HTTP request.
"""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app import config
from app.controllers import security as sec
from app.core import passwords, tokens
from app.db import utcnow
from app.errors import AppError
from app.models import RefreshToken, User
from app.models.user import ForgotPasswordIn, LoginIn, ResetPasswordIn, SignupIn, VerifyEmailIn

INVALID_LOGIN = AppError(401, "invalid_credentials", "Invalid username or password.")
UNAUTHORIZED = AppError(401, "unauthorized", "Please log in again.")


def _by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username.strip().lower()))


def _by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.strip().lower()))


def signup(db: Session, data: SignupIn) -> None:
    username, email = data.username.lower(), data.email.lower()
    taken = db.scalar(select(User.id).where(or_(User.username == username, User.email == email)))
    if taken is not None:
        # One message for both, so it can't be used to probe which emails are registered.
        raise AppError(409, "conflict", "That username or email is already in use.")
    user = User(
        username=username, email=email, password_hash=passwords.hash_password(data.password)
    )
    db.add(user)
    db.flush()
    sec.create_otp(db, user, "verify_email")
    db.commit()


def verify_email(db: Session, data: VerifyEmailIn, ip: str | None) -> tuple[dict, str]:
    user = _by_username(db, data.username)
    sec.verify_otp(db, user, "verify_email", data.code)
    user.email_verified = True
    payload, refresh = sec.start_session(db, user)
    sec.record_event(db, user.id, "login_ok", ip)
    db.commit()
    return payload, refresh


def resend_verification(db: Session, username: str) -> None:
    """Always looks the same from outside (no enumeration), cooldown included."""
    user = _by_username(db, username)
    if user is not None and not user.email_verified:
        sec.create_otp(db, user, "verify_email")
        db.commit()


def login(db: Session, data: LoginIn, ip: str | None) -> tuple[dict, str]:
    user = _by_username(db, data.username)
    if user is None:
        passwords.dummy_verify(data.password)  # same timing as a real check
        raise INVALID_LOGIN
    if sec.is_locked(user.login_locked_until):
        raise sec.too_many_attempts(user.login_locked_until)

    if not passwords.verify_password(user.password_hash, data.password):
        user.failed_login_count += 1
        sec.record_event(db, user.id, "login_failed", ip)
        if user.failed_login_count >= config.MAX_FAILED_ATTEMPTS:
            user.login_locked_until = sec.lock_until()
            user.failed_login_count = 0
            sec.record_event(db, user.id, "login_locked", ip)
            db.commit()
            raise sec.too_many_attempts(user.login_locked_until)
        db.commit()
        raise INVALID_LOGIN

    if not user.email_verified:
        raise AppError(403, "email_not_verified", "Verify your email first.")

    user.failed_login_count = 0
    user.login_locked_until = None
    if passwords.needs_rehash(user.password_hash):
        user.password_hash = passwords.hash_password(data.password)
    payload, refresh = sec.start_session(db, user)
    sec.record_event(db, user.id, "login_ok", ip)
    db.commit()
    return payload, refresh


def refresh(db: Session, token: str | None, ip: str | None) -> tuple[dict, str]:
    if not token:
        raise UNAUTHORIZED
    row = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == tokens.hash_refresh_token(token))
    )
    if row is None:
        raise UNAUTHORIZED
    if row.revoked_at is not None:
        # An already-used token came back: someone copied it. Kill the whole session.
        sec.revoke_session(db, row.session_id)
        sec.record_event(db, row.user_id, "refresh_reuse", ip)
        db.commit()
        raise UNAUTHORIZED
    user = db.get(User, row.user_id)
    if row.expires_at < utcnow() or user is None or not user.email_verified:
        raise UNAUTHORIZED
    row.revoked_at = utcnow()  # rotation: each token works once
    payload, new_refresh = sec.start_session(db, user, row.session_id)
    db.commit()
    return payload, new_refresh


def logout(db: Session, token: str | None) -> None:
    if not token:
        return
    row = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == tokens.hash_refresh_token(token))
    )
    if row is not None:
        sec.revoke_session(db, row.session_id)
        db.commit()


def forgot_password(db: Session, data: ForgotPasswordIn) -> None:
    user = _by_email(db, data.email)
    if user is not None and user.email_verified:
        sec.create_otp(db, user, "reset_password")
        db.commit()


def reset_password(db: Session, data: ResetPasswordIn, ip: str | None) -> None:
    user = _by_email(db, data.email)
    sec.verify_otp(db, user, "reset_password", data.code)
    user.password_hash = passwords.hash_password(data.new_password)
    user.failed_login_count = 0
    user.login_locked_until = None
    sec.revoke_user_sessions(db, user.id)
    sec.record_event(db, user.id, "password_changed", ip)
    db.commit()
