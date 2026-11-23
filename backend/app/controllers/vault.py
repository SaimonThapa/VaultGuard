"""Vault logic: set the master key, unlock, lock, status (product_backend.md §5.2).

Envelope encryption: a random DEK encrypts entries; the DEK is stored wrapped by a key derived
from the master key and again by one derived from the recovery key.
"""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import config
from app.controllers import security as sec
from app.core import crypto, key_store, passwords
from app.core.crypto import IntegrityError, KdfParams
from app.db import iso, utcnow
from app.dependencies import Unlocked
from app.errors import AppError
from app.models import Entry, User


def _params(user: User) -> KdfParams:
    return KdfParams(user.kdf_time_cost, user.kdf_memory_kib, user.kdf_parallelism)


def status(user: User, session_id: str) -> dict:
    locked_until = user.unlock_locked_until
    return {
        "set_up": user.vault_set_up,
        "unlocked": key_store.is_unlocked(session_id),
        "unlock_locked_until": iso(locked_until) if sec.is_locked(locked_until) else None,
        "idle_timeout_seconds": config.VAULT_IDLE_MINUTES * 60,
    }


def install_keys(user: User, master_key: str) -> tuple[bytes, str]:
    """Generate a DEK and wrap it under the master key and a fresh recovery key. Sets the key
    fields on `user` (the caller commits). Returns (dek, recovery_key)."""
    params = KdfParams(config.ARGON2_TIME_COST, config.ARGON2_MEMORY_KIB, config.ARGON2_PARALLELISM)
    dek = crypto.new_dek()
    user.kdf_time_cost = params.time_cost
    user.kdf_memory_kib = params.memory_kib
    user.kdf_parallelism = params.parallelism

    user.master_salt = crypto.new_salt()
    kek, user.master_verifier = crypto.derive_keys(master_key, user.master_salt, params)
    user.wrapped_dek_master = crypto.wrap_dek(kek, dek)

    recovery_key = crypto.new_recovery_key()
    user.recovery_salt = crypto.new_salt()
    recovery_kek, _ = crypto.derive_keys(
        crypto.normalize_recovery_key(recovery_key), user.recovery_salt, params
    )
    user.wrapped_dek_recovery = crypto.wrap_dek(recovery_kek, dek)
    return dek, recovery_key


def _reject_account_password(user: User, master_key: str) -> None:
    if passwords.verify_password(user.password_hash, master_key):
        # Two separate secrets: otherwise one leak opens both the account and the vault.
        raise AppError(
            422,
            "validation_error",
            "Choose a master key that differs from your account password.",
            fields=["master_key"],
        )


def setup(db: Session, user: User, session_id: str, master_key: str) -> str:
    if user.vault_set_up:
        raise AppError(409, "conflict", "Your vault is already set up.")
    _reject_account_password(user, master_key)
    dek, recovery_key = install_keys(user, master_key)
    db.commit()
    _, guesses_log10 = passwords.strength(master_key)
    key_store.put(session_id, user.id, dek, guesses_log10)
    return recovery_key


def verify_master_key(db: Session, user: User, master_key: str, ip: str | None) -> bytes:
    """Check a master key against the stored verifier and return its KEK. Failures count toward
    the unlock lockout (shared by unlock and export's step-up check)."""
    if not user.vault_set_up:
        raise AppError(409, "vault_not_set_up", "Set up your vault first.")
    if sec.is_locked(user.unlock_locked_until):  # checked first: no Argon2 time burned
        raise sec.too_many_attempts(user.unlock_locked_until)

    kek, verifier = crypto.derive_keys(master_key, user.master_salt, _params(user))
    if not crypto.verifier_matches(user.master_verifier, verifier):
        user.failed_unlock_count += 1
        sec.record_event(db, user.id, "unlock_failed", ip)
        if user.failed_unlock_count >= config.MAX_FAILED_ATTEMPTS:
            user.unlock_locked_until = sec.lock_until()
            user.failed_unlock_count = 0
            sec.record_event(db, user.id, "unlock_locked", ip)
            db.commit()
            raise sec.too_many_attempts(user.unlock_locked_until)
        db.commit()
        raise AppError(
            400,
            "invalid_master_key",
            "Wrong master key.",
            attempts_left=config.MAX_FAILED_ATTEMPTS - user.failed_unlock_count,
        )
    return kek


def unlock(db: Session, user: User, session_id: str, master_key: str, ip: str | None) -> dict:
    kek = verify_master_key(db, user, master_key, ip)
    try:
        dek = crypto.unwrap_dek(kek, user.wrapped_dek_master)
    except IntegrityError:
        # The key is right but the stored wrapped DEK fails its tag: the data was altered.
        sec.record_event(db, user.id, "tamper_detected", ip)
        db.commit()
        raise AppError(409, "integrity_failed", "Your vault failed its integrity check.") from None

    user.failed_unlock_count = 0
    user.unlock_locked_until = None
    sec.record_event(db, user.id, "unlock_ok", ip)
    db.commit()
    _, guesses_log10 = passwords.strength(master_key)
    key_store.put(session_id, user.id, dek, guesses_log10)
    return {"unlocked": True, "idle_timeout_seconds": config.VAULT_IDLE_MINUTES * 60}


def lock(session_id: str) -> None:
    key_store.drop(session_id)


# --- recovery, key change, reset (product_backend.md section 5.2) ---


def request_otp(db: Session, user: User, purpose: str) -> None:
    if purpose == "recover_master" and not user.vault_set_up:
        raise AppError(409, "vault_not_set_up", "Set up your vault first.")
    if not sec.create_otp(db, user, purpose):
        raise AppError(
            429,
            "too_many_attempts",
            "Wait a moment before asking for another code.",
            headers={"Retry-After": str(config.OTP_RESEND_SECONDS)},
        )
    db.commit()


def _wrap_under_new_master(user: User, dek: bytes, master_key: str) -> None:
    """Re-wrap the same DEK under a new master key, keeping the user's stored KDF parameters
    (the recovery wrap was derived with them, so they must not change here)."""
    user.master_salt = crypto.new_salt()
    kek, user.master_verifier = crypto.derive_keys(master_key, user.master_salt, _params(user))
    user.wrapped_dek_master = crypto.wrap_dek(kek, dek)


def recover(
    db: Session,
    user: User,
    session_id: str,
    code: str,
    recovery_key: str,
    new_master_key: str,
    ip: str | None,
) -> dict:
    """Forgot the master key: recovery key + emailed code -> same DEK under a new master key."""
    if not user.vault_set_up:
        raise AppError(409, "vault_not_set_up", "Set up your vault first.")
    if sec.is_locked(user.unlock_locked_until):
        raise sec.too_many_attempts(user.unlock_locked_until)
    otp = sec.verify_otp(db, user, "recover_master", code, consume=False)

    normalized = crypto.normalize_recovery_key(recovery_key)
    dek = None
    if normalized:
        recovery_kek, _ = crypto.derive_keys(normalized, user.recovery_salt, _params(user))
        try:
            dek = crypto.unwrap_dek(recovery_kek, user.wrapped_dek_recovery)
        except IntegrityError:
            dek = None
    if dek is None:  # a wrong key counts toward the unlock lockout; the emailed code stays valid
        user.failed_unlock_count += 1
        sec.record_event(db, user.id, "unlock_failed", ip)
        if user.failed_unlock_count >= config.MAX_FAILED_ATTEMPTS:
            user.unlock_locked_until = sec.lock_until()
            user.failed_unlock_count = 0
            sec.record_event(db, user.id, "unlock_locked", ip)
            db.commit()
            raise sec.too_many_attempts(user.unlock_locked_until)
        db.commit()
        raise AppError(
            400,
            "invalid_master_key",
            "That recovery key didn't work.",
            attempts_left=config.MAX_FAILED_ATTEMPTS - user.failed_unlock_count,
        )

    _reject_account_password(user, new_master_key)
    _wrap_under_new_master(user, dek, new_master_key)
    otp.used_at = utcnow()
    user.failed_unlock_count = 0
    user.unlock_locked_until = None
    sec.record_event(db, user.id, "master_key_recovered", ip)
    db.commit()
    _, guesses_log10 = passwords.strength(new_master_key)
    key_store.put(session_id, user.id, dek, guesses_log10)
    return {"unlocked": True}


def change_master_key(db: Session, unlocked: Unlocked, new_master_key: str, ip: str | None) -> str:
    """New DEK, every entry re-encrypted, new master wrap and a NEW recovery key, all in one
    transaction. Any failure (including a tampered entry) rolls everything back."""
    user = unlocked.user
    _reject_account_password(user, new_master_key)
    old_dek = unlocked.dek
    entries = db.scalars(select(Entry).where(Entry.user_id == user.id)).all()
    new_dek, recovery_key = install_keys(user, new_master_key)  # changes `user`, not yet saved
    try:
        for entry in entries:
            for column, name in (
                ("username_enc", "username"),
                ("password_enc", "password"),
                ("notes_enc", "notes"),
            ):
                blob = getattr(entry, column)
                if blob is None:
                    continue
                aad = crypto.field_aad(user.id, entry.id, name)
                plain = crypto.decrypt(old_dek, blob, aad)
                setattr(entry, column, crypto.encrypt(new_dek, plain, aad))
    except IntegrityError:
        db.rollback()  # nothing changed: the old master key and old recovery key still work
        sec.record_event(db, user.id, "tamper_detected", ip)
        db.commit()
        raise AppError(
            409, "integrity_failed", "Some entries failed their integrity check."
        ) from None

    sec.record_event(db, user.id, "master_key_changed", ip)
    db.commit()
    _, guesses_log10 = passwords.strength(new_master_key)
    key_store.drop_user(user.id)  # other sessions hold the old DEK
    key_store.put(unlocked.session_id, user.id, new_dek, guesses_log10)
    return recovery_key


def reset(
    db: Session, user: User, session_id: str, code: str, new_master_key: str, ip: str | None
) -> str:
    """Lost both keys: delete every entry and start the vault over (email code required)."""
    sec.verify_otp(db, user, "reset_vault", code)
    _reject_account_password(user, new_master_key)
    db.execute(delete(Entry).where(Entry.user_id == user.id))
    dek, recovery_key = install_keys(user, new_master_key)
    user.failed_unlock_count = 0
    user.unlock_locked_until = None
    sec.record_event(db, user.id, "vault_reset", ip)
    db.commit()
    _, guesses_log10 = passwords.strength(new_master_key)
    key_store.drop_user(user.id)
    key_store.put(session_id, user.id, dek, guesses_log10)
    return recovery_key
