"""Demo 1: tamper detection (OWASP A04). Edit one byte of stored ciphertext and it is noticed."""

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Entry, SecurityEvent, User

from .conftest import MASTER_KEY, new_entry, vault_user


def flip_byte(entry_id, column="password_enc", index=14):
    with SessionLocal() as db:
        row = db.get(Entry, entry_id)
        blob = bytearray(getattr(row, column))
        blob[index] ^= 1
        setattr(row, column, bytes(blob))
        db.commit()


def test_one_flipped_byte_is_detected_everywhere(client, outbox):
    headers, _ = vault_user(client, outbox)
    good = new_entry(client, headers, site_name="Good", password="Gh-Secret!2026-xyz-Alpha").json()
    bad = new_entry(client, headers, site_name="Bad").json()
    flip_byte(bad["id"])

    # list: the bad row is flagged, the others still decrypt, nothing crashes
    listed = {
        e["site_name"]: e for e in client.get("/api/entries", headers=headers).json()["entries"]
    }
    assert listed["Bad"]["integrity"] == "failed" and listed["Bad"]["password"] is None
    assert listed["Good"]["integrity"] == "ok"

    # read and update: refused with 409, never a 500
    assert client.get(f"/api/entries/{bad['id']}", headers=headers).status_code == 409
    put = client.put(
        f"/api/entries/{bad['id']}", json={"site_name": "x", "password": "y"}, headers=headers
    )
    assert put.status_code == 409
    assert client.get(f"/api/entries/{good['id']}", headers=headers).status_code == 200

    # health: flagged by id and name, and the score is capped in the red
    body = client.get("/api/vault/health", headers=headers).json()
    assert body["checks"]["integrity"]["failed"] == [{"id": bad["id"], "site_name": "Bad"}]
    assert body["checks"]["integrity"]["metric"] == 39  # critical, even with 1 of 2 intact
    assert body["checks"]["integrity"]["band"] == "critical"
    assert body["score"] <= 40 and body["band"] in ("critical", "poor")

    # logged for the activity log, with no secret in it
    with SessionLocal() as db:
        events = list(
            db.scalars(select(SecurityEvent).where(SecurityEvent.type == "tamper_detected"))
        )
        assert events and all(e.ip is not None or e.type for e in events)


def test_tampering_with_any_field_counts(client, outbox):
    headers, _ = vault_user(client, outbox)
    entry = new_entry(client, headers, notes="a note").json()
    flip_byte(entry["id"], column="notes_enc")
    body = client.get("/api/vault/health", headers=headers).json()
    assert body["checks"]["integrity"]["failed"][0]["id"] == entry["id"]


def test_a_clean_vault_is_not_capped(client, outbox):
    headers, _ = vault_user(client, outbox)
    new_entry(client, headers, password="Gh-Secret!2026-xyz-Alpha")
    body = client.get("/api/vault/health", headers=headers).json()
    assert body["checks"]["integrity"]["metric"] == 100 and body["score"] > 40


def test_tampered_wrapped_key_blocks_unlock_with_409(client, outbox):
    headers, _ = vault_user(client, outbox)
    client.post("/api/vault/lock", headers=headers)
    with SessionLocal() as db:
        user = db.scalar(select(User))
        blob = bytearray(user.wrapped_dek_master)
        blob[20] ^= 1
        user.wrapped_dek_master = bytes(blob)
        db.commit()
    res = client.post("/api/vault/unlock", json={"master_key": MASTER_KEY}, headers=headers)
    assert res.status_code == 409 and res.json()["error"] == "integrity_failed"


def test_ciphertext_copied_between_users_fails_its_tag_check(client, outbox):
    # AAD binds each field to user + entry + field, so moving a valid blob to another account fails.
    alice, _ = vault_user(client, outbox, "alice")
    bob_client = TestClient(app)
    bob, _ = vault_user(bob_client, outbox, "bob")
    a = new_entry(client, alice, password="alice-secret-1").json()
    b = new_entry(bob_client, bob, password="bob-secret-1").json()
    with SessionLocal() as db:
        db.get(Entry, b["id"]).password_enc = db.get(Entry, a["id"]).password_enc
        db.commit()
    assert bob_client.get(f"/api/entries/{b['id']}", headers=bob).status_code == 409
