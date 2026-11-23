"""Import (Chrome CSV or VaultGuard backup) and encrypted export (product_backend.md 5.4, 6.6).

Imports are hostile input: size and row caps, every row validated by the same schema as the API,
and failures reported by row number and field name only (never the value)."""

import base64
import binascii
import csv
import io
import json
import uuid
from datetime import UTC, datetime
from urllib.parse import urlsplit

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.controllers import entries as entry_logic
from app.controllers import security as sec
from app.controllers import vault as vault_logic
from app.core import crypto
from app.core.crypto import IntegrityError, KdfParams
from app.db import iso
from app.dependencies import Unlocked
from app.errors import AppError
from app.models import Entry
from app.models.entry import EntryIn

MAX_BYTES = 1024 * 1024  # 1 MB
MAX_ROWS = 2000
CSV_REQUIRED = {"name", "url", "username", "password"}
ENTRY_KEYS = ("site_name", "site_url", "username", "password", "notes", "rotation_days")
# A backup carries its own KDF parameters; cap them so a crafted file can't exhaust memory.
MAX_TIME_COST, MAX_MEMORY_KIB, MAX_PARALLELISM = 10, 262_144, 16


def _bad_file() -> AppError:
    return AppError(400, "invalid_import", "That file couldn't be imported.")


def _wrong_backup_key() -> AppError:
    return AppError(400, "invalid_master_key", "That master key doesn't open this backup.")


# --- parsing: each parser yields (row number, fields dict | failed field name) ---


def _csv_rows(text: str) -> list[tuple[int, dict | str]]:
    reader = csv.DictReader(io.StringIO(text))
    header = {(name or "").strip().lower(): name for name in (reader.fieldnames or [])}
    if not CSV_REQUIRED <= header.keys():
        raise _bad_file()
    rows = []
    for index, raw in enumerate(reader):
        if index >= MAX_ROWS:
            raise _bad_file()
        get = lambda key, raw=raw: (raw.get(header.get(key)) or "").strip()  # noqa: E731
        url = get("url")
        host = urlsplit(url if "://" in url else f"https://{url}").hostname if url else None
        rows.append(
            (
                index + 2,  # spreadsheet row: the header is row 1
                {
                    "site_name": get("name") or host or "",
                    "site_url": url or None,
                    "username": raw.get(header["username"]) or "",
                    "password": raw.get(header["password"]) or "",
                    "notes": get("note") or None,
                },
            )
        )
    return rows


def _b64(value) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, TypeError, ValueError):
        raise _bad_file() from None


def _backup_rows(text: str, master_key: str | None) -> list[tuple[int, dict | str]]:
    try:
        doc = json.loads(text)
        kdf = doc["kdf"]
        params = KdfParams(int(kdf["time_cost"]), int(kdf["memory_kib"]), int(kdf["parallelism"]))
        salt, verifier, wrapped = _b64(kdf["salt"]), _b64(doc["verifier"]), _b64(doc["wrapped_dek"])
        items = doc["entries"]
        ok = (
            doc["format"] == "vaultguard-backup"
            and doc["version"] == 1
            and kdf["alg"] == "argon2id"
            and isinstance(items, list)
            and len(items) <= MAX_ROWS
            and 1 <= params.time_cost <= MAX_TIME_COST
            and 8 <= params.memory_kib <= MAX_MEMORY_KIB
            and 1 <= params.parallelism <= MAX_PARALLELISM
        )
    except (ValueError, KeyError, TypeError, AttributeError):
        raise _bad_file() from None
    if not ok:
        raise _bad_file()
    if not master_key:
        raise _wrong_backup_key()

    kek, check = crypto.derive_keys(master_key, salt, params)
    if not crypto.verifier_matches(verifier, check):
        raise _wrong_backup_key()
    try:
        dek = crypto.unwrap_dek(kek, wrapped)
    except IntegrityError:
        raise _bad_file() from None

    rows = []
    for index, item in enumerate(items):
        try:
            blob = _b64(item["fields"])
            fields = json.loads(crypto.decrypt(dek, blob, f"backup|{item['id']}"))
            rows.append((index + 1, {k: fields.get(k) for k in ENTRY_KEYS if k in fields}))
        except (IntegrityError, KeyError, TypeError, ValueError, AppError):
            rows.append((index + 1, "integrity"))  # this row was altered; the rest still import
    return rows


# --- import ---


def import_file(
    db: Session, unlocked: Unlocked, raw: bytes, master_key: str | None, ip: str | None
) -> dict:
    if len(raw) > MAX_BYTES:
        raise _bad_file()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise _bad_file() from None
    rows = _backup_rows(text, master_key) if text.lstrip().startswith("{") else _csv_rows(text)

    # What the vault already holds (decrypted in memory only), to skip exact duplicates.
    seen = set()
    for entry in db.scalars(entry_logic.owned_entries(unlocked.user.id)):
        try:
            f = entry_logic.decrypted(unlocked, entry)
        except IntegrityError:
            continue
        seen.add((entry.site_name, entry.site_url, f["username"], f["password"]))

    fresh, failed, skipped = [], [], 0
    for row_no, fields in rows:
        if isinstance(fields, str):
            failed.append({"row": row_no, "reason": fields})
            continue
        try:
            data = EntryIn(**fields)
        except (ValidationError, TypeError) as exc:
            reason = str(exc.errors()[0]["loc"][-1]) if isinstance(exc, ValidationError) else "row"
            failed.append({"row": row_no, "reason": reason})  # field name only, never the value
            continue
        key = (data.site_name, data.site_url, data.username, data.password)
        if key in seen:
            skipped += 1
            continue
        seen.add(key)
        fresh.append(data)

    for data in fresh:  # one transaction: all or nothing
        entry = Entry(id=str(uuid.uuid4()), user_id=unlocked.user.id)
        entry_logic.encrypt_into(entry, unlocked, data)
        db.add(entry)
    sec.record_event(db, unlocked.user.id, "import", ip)
    db.commit()
    return {"imported": len(fresh), "skipped_duplicates": skipped, "failed_rows": failed}


# --- export ---


def export_backup(
    db: Session, unlocked: Unlocked, master_key: str, ip: str | None
) -> tuple[str, str]:
    """Re-check the master key (a step-up: an unattended unlocked session can't dump the vault),
    then return (filename, JSON). Everything in the file is encrypted, site names included."""
    user = unlocked.user
    vault_logic.verify_master_key(db, user, master_key, ip)

    items, skipped = [], 0
    for entry in db.scalars(entry_logic.owned_entries(user.id)):
        try:
            f = entry_logic.decrypted(unlocked, entry)
        except IntegrityError:
            skipped += 1
            continue
        payload = {
            "site_name": f["site_name"],
            "site_url": f["site_url"],
            "username": f["username"],
            "password": f["password"],
            "notes": f["notes"],
            "rotation_days": f["rotation_days"],
        }
        blob = crypto.encrypt(unlocked.dek, json.dumps(payload), f"backup|{entry.id}")
        items.append({"id": entry.id, "fields": base64.b64encode(blob).decode()})

    if skipped:
        sec.record_event(db, user.id, "tamper_detected", ip)
    sec.record_event(db, user.id, "export", ip)
    db.commit()

    now = datetime.now(UTC)
    backup = {
        "format": "vaultguard-backup",
        "version": 1,
        "created_at": iso(now.replace(tzinfo=None)),
        "kdf": {
            "alg": "argon2id",
            "time_cost": user.kdf_time_cost,
            "memory_kib": user.kdf_memory_kib,
            "parallelism": user.kdf_parallelism,
            "salt": base64.b64encode(user.master_salt).decode(),
        },
        "verifier": base64.b64encode(user.master_verifier).decode(),
        "wrapped_dek": base64.b64encode(user.wrapped_dek_master).decode(),
        "skipped_integrity": skipped,
        "entries": items,
    }
    return f"vaultguard-backup-{now:%Y%m%d}.json", json.dumps(backup)
