"""Recovery, master-key change, vault reset and account password change."""

from fastapi.testclient import TestClient
from sqlalchemy import select

from app import config
from app.db import SessionLocal
from app.main import app
from app.models import Entry, SecurityEvent, User

from .conftest import (
    MASTER_KEY,
    STRONG_PASSWORD,
    auth_header,
    last_code,
    new_entry,
    signup_and_verify,
    vault_user,
)

NEW_KEY = "Zq8-orbit-lantern-9-velvet-harbor-Mx"
OTHER_KEY = "Another-Very-Long-Master-Key-77!"


def ask_code(client, headers, outbox, purpose, user="alice"):
    res = client.post("/api/vault/otp", json={"purpose": purpose}, headers=headers)
    assert res.status_code == 202, res.text
    return last_code(outbox, f"{user}@demo.mail")


def unlock(client, headers, key):
    return client.post("/api/vault/unlock", json={"master_key": key}, headers=headers)


# --- recover with recovery key + OTP ---


def test_recover_with_recovery_key_keeps_old_entries_readable(client, outbox):
    headers, recovery_key = vault_user(client, outbox)
    new_entry(client, headers, password="keep-me-readable-1")
    client.post("/api/vault/lock", headers=headers)

    code = ask_code(client, headers, outbox, "recover_master")
    body = {"code": code, "recovery_key": recovery_key.lower(), "new_master_key": NEW_KEY}
    res = client.post("/api/vault/recover", json=body, headers=headers)
    assert res.status_code == 200 and res.json() == {"unlocked": True}

    assert client.get("/api/entries", headers=headers).json()["entries"][0]["password"] == (
        "keep-me-readable-1"
    )
    client.post("/api/vault/lock", headers=headers)
    assert unlock(client, headers, MASTER_KEY).status_code == 400  # old master key is dead
    assert unlock(client, headers, NEW_KEY).status_code == 200
    with SessionLocal() as db:
        assert db.scalar(select(SecurityEvent).where(SecurityEvent.type == "master_key_recovered"))


def test_recover_recovery_key_stays_valid_afterwards(client, outbox, monkeypatch):
    headers, recovery_key = vault_user(client, outbox)
    for key in (NEW_KEY, OTHER_KEY):
        monkeypatch.setattr(config, "OTP_RESEND_SECONDS", 0)
        code = ask_code(client, headers, outbox, "recover_master")
        res = client.post(
            "/api/vault/recover",
            json={"code": code, "recovery_key": recovery_key, "new_master_key": key},
            headers=headers,
        )
        assert res.status_code == 200


def test_recover_wrong_recovery_key_is_400_counts_attempts_and_keeps_the_code(client, outbox):
    headers, recovery_key = vault_user(client, outbox)
    code = ask_code(client, headers, outbox, "recover_master")
    bad = client.post(
        "/api/vault/recover",
        json={
            "code": code,
            "recovery_key": "AAAA-AAAA-AAAA-AAAA-AAAA-AAAA-AA",
            "new_master_key": NEW_KEY,
        },
        headers=headers,
    )
    assert bad.status_code == 400
    assert bad.json()["error"] == "invalid_master_key"
    assert bad.json()["attempts_left"] == config.MAX_FAILED_ATTEMPTS - 1

    ok = client.post(
        "/api/vault/recover",
        json={"code": code, "recovery_key": recovery_key, "new_master_key": NEW_KEY},
        headers=headers,
    )  # the same emailed code still works
    assert ok.status_code == 200


def test_recover_malformed_recovery_key_is_the_same_400(client, outbox):
    headers, _ = vault_user(client, outbox)
    code = ask_code(client, headers, outbox, "recover_master")
    res = client.post(
        "/api/vault/recover",
        json={"code": code, "recovery_key": "not a key", "new_master_key": NEW_KEY},
        headers=headers,
    )
    assert res.status_code == 400 and res.json()["error"] == "invalid_master_key"


def test_recover_wrong_otp_is_400_invalid_otp(client, outbox):
    headers, recovery_key = vault_user(client, outbox)
    ask_code(client, headers, outbox, "recover_master")
    res = client.post(
        "/api/vault/recover",
        json={"code": "000000", "recovery_key": recovery_key, "new_master_key": NEW_KEY},
        headers=headers,
    )
    assert res.status_code == 400 and res.json()["error"] == "invalid_otp"


def test_recover_locks_out_after_five_wrong_recovery_keys(client, outbox):
    headers, recovery_key = vault_user(client, outbox)
    code = ask_code(client, headers, outbox, "recover_master")
    wrong = {
        "code": code,
        "recovery_key": "BBBB-BBBB-BBBB-BBBB-BBBB-BBBB-BB",
        "new_master_key": NEW_KEY,
    }
    statuses = [
        client.post("/api/vault/recover", json=wrong, headers=headers).status_code for _ in range(5)
    ]
    assert statuses == [400, 400, 400, 400, 429]
    right = {**wrong, "recovery_key": recovery_key}
    assert client.post("/api/vault/recover", json=right, headers=headers).status_code == 429


def test_an_otp_for_one_purpose_cannot_be_used_for_another(client, outbox):
    headers, recovery_key = vault_user(client, outbox)
    code = ask_code(client, headers, outbox, "reset_vault")
    res = client.post(
        "/api/vault/recover",
        json={"code": code, "recovery_key": recovery_key, "new_master_key": NEW_KEY},
        headers=headers,
    )
    assert res.status_code == 400 and res.json()["error"] == "invalid_otp"


def test_otp_request_cooldown_is_429_with_retry_after(client, outbox):
    headers, _ = vault_user(client, outbox)
    ask_code(client, headers, outbox, "recover_master")
    res = client.post("/api/vault/otp", json={"purpose": "recover_master"}, headers=headers)
    assert res.status_code == 429 and int(res.headers["retry-after"]) > 0


def test_otp_purpose_is_validated(client, outbox):
    headers, _ = vault_user(client, outbox)
    res = client.post("/api/vault/otp", json={"purpose": "verify_email"}, headers=headers)
    assert res.status_code == 422


def test_new_master_key_must_differ_from_the_account_password(client, outbox):
    headers, recovery_key = vault_user(client, outbox)
    code = ask_code(client, headers, outbox, "recover_master")
    res = client.post(
        "/api/vault/recover",
        json={"code": code, "recovery_key": recovery_key, "new_master_key": STRONG_PASSWORD},
        headers=headers,
    )
    assert res.status_code == 422 and res.json()["fields"] == ["master_key"]


# --- change master key ---


def test_change_master_key_reencrypts_everything_and_kills_the_old_recovery_key(client, outbox):
    headers, old_recovery = vault_user(client, outbox)
    for i in range(3):
        new_entry(client, headers, site_name=f"Site {i}", password=f"pw-number-{i}-xyz", notes="n")
    with SessionLocal() as db:
        before = {e.id: e.password_enc for e in db.scalars(select(Entry))}

    res = client.post(
        "/api/vault/change-master-key", json={"new_master_key": NEW_KEY}, headers=headers
    )
    assert res.status_code == 200
    new_recovery = res.json()["recovery_key"]
    assert new_recovery != old_recovery

    with SessionLocal() as db:
        after = {e.id: e.password_enc for e in db.scalars(select(Entry))}
    assert before.keys() == after.keys() and all(before[k] != after[k] for k in before)

    entries = client.get("/api/entries", headers=headers).json()["entries"]
    assert sorted(e["password"] for e in entries) == [
        "pw-number-0-xyz",
        "pw-number-1-xyz",
        "pw-number-2-xyz",
    ]

    client.post("/api/vault/lock", headers=headers)
    assert unlock(client, headers, MASTER_KEY).status_code == 400  # old master key
    assert unlock(client, headers, NEW_KEY).status_code == 200
    assert client.get("/api/entries", headers=headers).json()["entries"][0]["integrity"] == "ok"

    code = ask_code(client, headers, outbox, "recover_master")
    old = client.post(
        "/api/vault/recover",
        json={"code": code, "recovery_key": old_recovery, "new_master_key": OTHER_KEY},
        headers=headers,
    )
    assert old.status_code == 400  # the old recovery key no longer works
    good = client.post(
        "/api/vault/recover",
        json={"code": code, "recovery_key": new_recovery, "new_master_key": OTHER_KEY},
        headers=headers,
    )
    assert good.status_code == 200


def test_change_master_key_rolls_back_completely_on_a_tampered_entry(client, outbox):
    headers, old_recovery = vault_user(client, outbox)
    entry = new_entry(client, headers).json()
    with SessionLocal() as db:
        row = db.get(Entry, entry["id"])
        blob = bytearray(row.password_enc)
        blob[14] ^= 1
        row.password_enc = bytes(blob)
        db.commit()
        snapshot = (row.password_enc, row.username_enc, db.scalar(select(User)).wrapped_dek_master)

    res = client.post(
        "/api/vault/change-master-key", json={"new_master_key": NEW_KEY}, headers=headers
    )
    assert res.status_code == 409 and res.json()["error"] == "integrity_failed"

    with SessionLocal() as db:
        row = db.get(Entry, entry["id"])
        assert (
            row.password_enc,
            row.username_enc,
            db.scalar(select(User)).wrapped_dek_master,
        ) == snapshot
    client.post("/api/vault/lock", headers=headers)
    assert unlock(client, headers, MASTER_KEY).status_code == 200  # nothing changed


def test_change_master_key_needs_an_unlocked_vault(client, outbox):
    headers, _ = vault_user(client, outbox)
    client.post("/api/vault/lock", headers=headers)
    res = client.post(
        "/api/vault/change-master-key", json={"new_master_key": NEW_KEY}, headers=headers
    )
    assert res.status_code == 423


def test_change_master_key_drops_other_sessions_vault_keys(client, outbox):
    headers, _ = vault_user(client, outbox)
    other = TestClient(app)  # a second browser
    login = other.post(
        "/api/auth/login", json={"username": "alice", "password": STRONG_PASSWORD}
    ).json()
    other_headers = auth_header(login)
    assert unlock(other, other_headers, MASTER_KEY).status_code == 200

    client.post("/api/vault/change-master-key", json={"new_master_key": NEW_KEY}, headers=headers)
    assert other.get("/api/vault/status", headers=other_headers).json()["unlocked"] is False
    assert client.get("/api/vault/status", headers=headers).json()["unlocked"] is True


# --- reset vault ---


def test_reset_vault_wipes_entries_and_starts_over(client, outbox):
    headers, old_recovery = vault_user(client, outbox)
    new_entry(client, headers)
    new_entry(client, headers)
    client.post("/api/vault/lock", headers=headers)

    code = ask_code(client, headers, outbox, "reset_vault")
    res = client.post(
        "/api/vault/reset", json={"code": code, "new_master_key": NEW_KEY}, headers=headers
    )
    assert res.status_code == 200 and res.json()["recovery_key"] != old_recovery

    body = client.get("/api/entries", headers=headers).json()
    assert body["locked"] is False and body["entries"] == []
    new_entry(client, headers)  # the fresh vault works
    client.post("/api/vault/lock", headers=headers)
    assert unlock(client, headers, NEW_KEY).status_code == 200
    with SessionLocal() as db:
        assert db.scalar(select(SecurityEvent).where(SecurityEvent.type == "vault_reset"))


def test_reset_vault_requires_a_valid_code_and_never_deletes_without_it(client, outbox):
    headers, _ = vault_user(client, outbox)
    new_entry(client, headers)
    ask_code(client, headers, outbox, "reset_vault")
    res = client.post(
        "/api/vault/reset", json={"code": "000000", "new_master_key": NEW_KEY}, headers=headers
    )
    assert res.status_code == 400
    with SessionLocal() as db:
        assert len(db.scalars(select(Entry)).all()) == 1


def test_reset_vault_only_deletes_the_callers_entries(client, outbox):
    alice, _ = vault_user(client, outbox, "alice")
    bob_client = TestClient(app)
    bob, _ = vault_user(bob_client, outbox, "bob")
    new_entry(bob_client, bob)
    new_entry(client, alice)
    code = ask_code(client, alice, outbox, "reset_vault")
    client.post("/api/vault/reset", json={"code": code, "new_master_key": NEW_KEY}, headers=alice)
    assert len(bob_client.get("/api/entries", headers=bob).json()["entries"]) == 1


# --- change account password ---

NEW_PASSWORD = "Fresh-Account-Passphrase-42"


def test_change_password_signs_out_other_sessions_but_not_this_one(client, outbox):
    headers, _ = vault_user(client, outbox)
    other = TestClient(app)
    other.post("/api/auth/login", json={"username": "alice", "password": STRONG_PASSWORD})

    res = client.post(
        "/api/account/change-password",
        json={"current_password": STRONG_PASSWORD, "new_password": NEW_PASSWORD},
        headers=headers,
    )
    assert res.status_code == 200
    assert client.get("/api/vault/status", headers=headers).status_code == 200  # still signed in
    assert other.post("/api/auth/refresh").status_code == 401  # the other browser is out

    login = lambda pw: client.post("/api/auth/login", json={"username": "alice", "password": pw})  # noqa: E731
    assert login(STRONG_PASSWORD).status_code == 401
    assert login(NEW_PASSWORD).status_code == 200
    assert unlock(client, headers, MASTER_KEY).status_code == 200  # vault untouched


def test_change_password_wrong_current_is_400_and_counts_toward_lockout(client, outbox):
    headers = auth_header(signup_and_verify(client, outbox))
    body = {"current_password": "wrong-current-pw", "new_password": NEW_PASSWORD}
    codes = [
        client.post("/api/account/change-password", json=body, headers=headers).status_code
        for _ in range(5)
    ]
    assert codes == [400, 400, 400, 400, 429]
    assert (
        client.post(
            "/api/auth/login", json={"username": "alice", "password": STRONG_PASSWORD}
        ).status_code
        == 429
    )


def test_change_password_rejects_a_weak_new_password(client, outbox):
    headers = auth_header(signup_and_verify(client, outbox))
    res = client.post(
        "/api/account/change-password",
        json={"current_password": STRONG_PASSWORD, "new_password": "password1234"},
        headers=headers,
    )
    assert res.status_code == 422
