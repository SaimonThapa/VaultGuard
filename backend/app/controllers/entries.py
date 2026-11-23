"""Entry logic: list/search, create, read, update, delete (product_backend.md §5.3).

Every query goes through `owned_entries` / `get_owned_entry`, so a user can only ever see their
own rows. That single rule is the IDOR defense.
"""

import base64
import uuid
from datetime import timedelta

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.controllers import security as sec
from app.core import crypto
from app.core.crypto import IntegrityError
from app.db import iso, utcnow
from app.dependencies import Unlocked
from app.errors import AppError
from app.models import Entry
from app.models.entry import EntryIn

NOT_FOUND = AppError(404, "not_found", "Not found.")
INTEGRITY = AppError(409, "integrity_failed", "This entry failed its integrity check.")
MAX_LIST = 2000
HIDDEN = dict.fromkeys(("username", "password", "notes"))  # all None: nothing to show


def owned_entries(user_id: int) -> Select:
    """The only way to start an entries query: always filtered by owner."""
    return select(Entry).where(Entry.user_id == user_id)


def get_owned_entry(db: Session, user_id: int, entry_id: str) -> Entry:
    """WHERE id = :id AND user_id = :uid. Missing and not-yours both give 404 (no leak)."""
    entry = db.scalar(owned_entries(user_id).where(Entry.id == entry_id))
    if entry is None:
        raise NOT_FOUND
    return entry


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _field(unlocked: Unlocked, entry: Entry, name: str, blob: bytes | None) -> str | None:
    if blob is None:
        return None
    aad = crypto.field_aad(unlocked.user.id, entry.id, name)
    return crypto.decrypt(unlocked.dek, blob, aad)


def _rotation_due(entry: Entry) -> bool:
    if entry.rotation_days is None:
        return False
    return utcnow() - entry.password_changed_at > timedelta(days=entry.rotation_days)


def _base(entry: Entry) -> dict:
    return {
        "id": entry.id,
        "site_name": entry.site_name,
        "site_url": entry.site_url,
        "rotation_days": entry.rotation_days,
        "password_changed_at": iso(entry.password_changed_at),
        "rotation_due": _rotation_due(entry),
        "created_at": iso(entry.created_at),
        "updated_at": iso(entry.updated_at),
    }


def decrypted(unlocked: Unlocked, entry: Entry) -> dict:
    """Full entry. Raises IntegrityError if any field fails its tag check."""
    return {
        **_base(entry),
        "username": _field(unlocked, entry, "username", entry.username_enc),
        "password": _field(unlocked, entry, "password", entry.password_enc),
        "notes": _field(unlocked, entry, "notes", entry.notes_enc),
        "integrity": "ok",
    }


def locked_view(entry: Entry) -> dict:
    """What a locked vault shows: no secrets, only a ciphertext preview (safe to display)."""
    preview = base64.b64encode(entry.password_enc).decode()[:24]
    return {**_base(entry), **HIDDEN, "ciphertext_preview": preview, "integrity": "unknown"}


def tampered_view(entry: Entry) -> dict:
    return {**_base(entry), **HIDDEN, "integrity": "failed"}


def list_entries(db: Session, user_id: int, unlocked: Unlocked | None, q: str, ip: str | None):
    query = owned_entries(user_id)
    if q:
        pattern = f"%{_escape_like(q.lower())}%"
        # Bound parameters only: q is data, never part of the SQL text (SQL-injection defense).
        query = query.where(
            func.lower(Entry.site_name).like(pattern, escape="\\")
            | func.lower(func.coalesce(Entry.site_url, "")).like(pattern, escape="\\")
        )
    rows = db.scalars(
        query.order_by(func.lower(Entry.site_name), Entry.created_at).limit(MAX_LIST)
    ).all()

    if unlocked is None:
        return {"locked": True, "entries": [locked_view(e) for e in rows]}

    out, tampered = [], False
    for entry in rows:
        try:
            out.append(decrypted(unlocked, entry))
        except IntegrityError:
            tampered = True
            out.append(tampered_view(entry))
    if tampered:  # once per request, however many rows are bad
        sec.record_event(db, user_id, "tamper_detected", ip)
        db.commit()
    return {"locked": False, "entries": out}


def encrypt_into(entry: Entry, unlocked: Unlocked, data: EntryIn) -> None:
    uid, key = unlocked.user.id, unlocked.dek
    entry.site_name = data.site_name
    entry.site_url = data.site_url
    entry.rotation_days = data.rotation_days
    entry.username_enc = crypto.encrypt(
        key, data.username, crypto.field_aad(uid, entry.id, "username")
    )
    entry.password_enc = crypto.encrypt(
        key, data.password, crypto.field_aad(uid, entry.id, "password")
    )
    entry.notes_enc = (
        crypto.encrypt(key, data.notes, crypto.field_aad(uid, entry.id, "notes"))
        if data.notes
        else None
    )


def create(db: Session, unlocked: Unlocked, data: EntryIn) -> dict:
    entry = Entry(id=str(uuid.uuid4()), user_id=unlocked.user.id)
    encrypt_into(entry, unlocked, data)
    db.add(entry)
    db.commit()
    return decrypted(unlocked, entry)


def read(db: Session, unlocked: Unlocked, entry_id: str, ip: str | None) -> dict:
    entry = get_owned_entry(db, unlocked.user.id, entry_id)
    try:
        return decrypted(unlocked, entry)
    except IntegrityError:
        sec.record_event(db, unlocked.user.id, "tamper_detected", ip)
        db.commit()
        raise INTEGRITY from None


def update(db: Session, unlocked: Unlocked, entry_id: str, data: EntryIn, ip: str | None) -> dict:
    entry = get_owned_entry(db, unlocked.user.id, entry_id)
    try:
        old_password = _field(unlocked, entry, "password", entry.password_enc)
    except IntegrityError:
        sec.record_event(db, unlocked.user.id, "tamper_detected", ip)
        db.commit()
        raise INTEGRITY from None
    if old_password != data.password:
        entry.password_changed_at = utcnow()
    encrypt_into(entry, unlocked, data)  # fresh nonces on every write
    db.commit()
    return decrypted(unlocked, entry)


def delete(db: Session, user_id: int, entry_id: str) -> None:
    entry = get_owned_entry(db, user_id, entry_id)
    db.delete(entry)
    db.commit()
