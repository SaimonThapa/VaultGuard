"""Account logic: change the account password (product_backend.md section 5.5)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.controllers import security as sec
from app.core import passwords
from app.db import iso
from app.dependencies import CurrentSession
from app.errors import AppError
from app.models import SecurityEvent
from app.models.user import ChangePasswordIn


def change_password(db: Session, session: CurrentSession, data: ChangePasswordIn, ip: str | None):
    user = session.user
    if sec.is_locked(user.login_locked_until):
        raise sec.too_many_attempts(user.login_locked_until)

    if not passwords.verify_password(user.password_hash, data.current_password):
        # 400, not 401: the session is fine, so the frontend must not run its logout logic.
        user.failed_login_count += 1
        sec.record_event(db, user.id, "login_failed", ip)
        if user.failed_login_count >= config.MAX_FAILED_ATTEMPTS:
            user.login_locked_until = sec.lock_until()
            user.failed_login_count = 0
            sec.record_event(db, user.id, "login_locked", ip)
            db.commit()
            raise sec.too_many_attempts(user.login_locked_until)
        db.commit()
        raise AppError(400, "invalid_credentials", "Your current password is wrong.")

    score, _ = passwords.strength(data.new_password, [user.username, user.email])
    if score < 3:
        raise AppError(422, "validation_error", "Some fields are invalid.", fields=["new_password"])

    user.password_hash = passwords.hash_password(data.new_password)
    user.failed_login_count = 0
    sec.revoke_user_sessions(
        db, user.id, except_session=session.session_id
    )  # the vault is unaffected
    sec.record_event(db, user.id, "password_changed", ip)
    db.commit()


def activity(db: Session, user_id: int, limit: int) -> dict:
    """The caller's own security events, newest first. Events never contain secrets."""
    rows = db.scalars(
        select(SecurityEvent)
        .where(SecurityEvent.user_id == user_id)
        .order_by(SecurityEvent.id.desc())
        .limit(limit)
    )
    return {"events": [{"type": e.type, "ip": e.ip, "created_at": iso(e.created_at)} for e in rows]}
