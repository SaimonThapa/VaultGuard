from datetime import timedelta

from sqlalchemy import select

from app.db import SessionLocal, utcnow
from app.models import Entry, SecurityEvent

from .conftest import MASTER_KEY, new_entry, vault_user


def test_create_returns_decrypted_entry_and_normalizes_the_url(client, outbox):
    headers, _ = vault_user(client, outbox)
    res = new_entry(client, headers, notes="<script>alert(1)</script>")
    assert res.status_code == 201
    body = res.json()
    assert body["site_url"] == "https://github.com"
    assert body["username"] == "alice-dev" and body["password"] == "S3cret!pass-one"
    assert body["notes"] == "<script>alert(1)</script>"  # stored as text; the UI never renders HTML
    assert body["integrity"] == "ok"


def test_database_stores_ciphertext_not_plaintext(client, outbox):
    headers, _ = vault_user(client, outbox)
    new_entry(client, headers, notes="top secret note")
    with SessionLocal() as db:
        row = db.scalar(select(Entry))
        raw = row.username_enc + row.password_enc + row.notes_enc
        for plain in (b"alice-dev", b"S3cret!pass-one", b"top secret note"):
            assert plain not in raw
        assert row.site_name == "GitHub"  # site name/URL stay searchable by design


def test_locked_list_shows_ciphertext_preview_only(client, outbox):
    headers, _ = vault_user(client, outbox)
    new_entry(client, headers)
    client.post("/api/vault/lock", headers=headers)
    body = client.get("/api/entries", headers=headers).json()
    entry = body["entries"][0]
    assert body["locked"] is True
    assert entry["username"] is None and entry["password"] is None and entry["notes"] is None
    assert len(entry["ciphertext_preview"]) == 24
    assert "S3cret" not in str(body)


def test_unlocked_list_is_decrypted_and_sorted_case_insensitively(client, outbox):
    headers, _ = vault_user(client, outbox)
    for name in ("zoom", "Amazon", "bank"):
        new_entry(client, headers, site_name=name)
    body = client.get("/api/entries", headers=headers).json()
    assert body["locked"] is False
    assert [e["site_name"] for e in body["entries"]] == ["Amazon", "bank", "zoom"]
    assert body["entries"][0]["password"] == "S3cret!pass-one"


def test_search_matches_site_name_and_url_case_insensitively(client, outbox):
    headers, _ = vault_user(client, outbox)
    new_entry(client, headers, site_name="GitHub", site_url="github.com")
    new_entry(client, headers, site_name="Mail", site_url="https://fastmail.com")

    def names(q):
        res = client.get("/api/entries", params={"q": q}, headers=headers)
        return [e["site_name"] for e in res.json()["entries"]]

    assert names("GITHUB") == ["GitHub"]
    assert names("fastmail") == ["Mail"]
    assert names("nothing") == []


def test_update_changes_password_timestamp_only_when_password_changes(client, outbox):
    headers, _ = vault_user(client, outbox)
    entry = new_entry(client, headers).json()
    with SessionLocal() as db:
        row = db.get(Entry, entry["id"])
        row.password_changed_at = utcnow() - timedelta(days=100)
        old_blob = row.password_enc
        db.commit()
        stamp = row.password_changed_at

    body = {"site_name": "GitHub", "username": "renamed", "password": "S3cret!pass-one"}
    res = client.put(f"/api/entries/{entry['id']}", json=body, headers=headers)
    assert res.status_code == 200 and res.json()["username"] == "renamed"
    with SessionLocal() as db:
        row = db.get(Entry, entry["id"])
        assert row.password_changed_at == stamp  # same password: not "changed"
        assert row.password_enc != old_blob  # but fresh nonce on every write

    client.put(
        f"/api/entries/{entry['id']}", json={**body, "password": "Brand-new-pw-2"}, headers=headers
    )
    with SessionLocal() as db:
        assert db.get(Entry, entry["id"]).password_changed_at > stamp


def test_rotation_due_flag(client, outbox):
    headers, _ = vault_user(client, outbox)
    entry = new_entry(client, headers, rotation_days=30).json()
    assert entry["rotation_due"] is False
    with SessionLocal() as db:
        db.get(Entry, entry["id"]).password_changed_at = utcnow() - timedelta(days=31)
        db.commit()
    assert client.get(f"/api/entries/{entry['id']}", headers=headers).json()["rotation_due"] is True


def test_delete_then_404(client, outbox):
    headers, _ = vault_user(client, outbox)
    entry = new_entry(client, headers).json()
    assert client.delete(f"/api/entries/{entry['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/entries/{entry['id']}", headers=headers).status_code == 404
    assert client.delete(f"/api/entries/{entry['id']}", headers=headers).status_code == 404


def test_duplicates_are_allowed(client, outbox):
    headers, _ = vault_user(client, outbox)
    new_entry(client, headers)
    new_entry(client, headers)
    assert len(client.get("/api/entries", headers=headers).json()["entries"]) == 2


def test_tampered_entry_is_flagged_without_breaking_the_list(client, outbox):
    headers, _ = vault_user(client, outbox)
    good = new_entry(client, headers, site_name="Good").json()
    bad = new_entry(client, headers, site_name="Bad").json()
    with SessionLocal() as db:
        row = db.get(Entry, bad["id"])
        blob = bytearray(row.password_enc)
        blob[14] ^= 1
        row.password_enc = bytes(blob)
        db.commit()

    listed = client.get("/api/entries", headers=headers)
    assert listed.status_code == 200
    by_name = {e["site_name"]: e for e in listed.json()["entries"]}
    assert by_name["Bad"]["integrity"] == "failed" and by_name["Bad"]["password"] is None
    assert by_name["Good"]["integrity"] == "ok" and by_name["Good"]["password"]

    assert client.get(f"/api/entries/{bad['id']}", headers=headers).status_code == 409
    assert client.get(f"/api/entries/{good['id']}", headers=headers).status_code == 200
    with SessionLocal() as db:
        assert db.scalar(select(SecurityEvent).where(SecurityEvent.type == "tamper_detected"))


def test_ciphertext_moved_to_another_field_fails_its_tag_check(client, outbox):
    headers, _ = vault_user(client, outbox)
    entry = new_entry(client, headers).json()
    with SessionLocal() as db:
        row = db.get(Entry, entry["id"])
        row.username_enc = row.password_enc  # valid ciphertext, wrong field
        db.commit()
    assert client.get(f"/api/entries/{entry['id']}", headers=headers).status_code == 409


def test_master_key_is_never_needed_again_after_unlock(client, outbox):
    headers, _ = vault_user(client, outbox)
    assert MASTER_KEY not in client.get("/api/vault/status", headers=headers).text
