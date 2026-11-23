import pytest
from sqlalchemy import select

from app import config
from app.core import crypto
from app.core.crypto import KdfParams
from app.db import SessionLocal
from app.models import SecurityEvent, User

from .conftest import MASTER_KEY, STRONG_PASSWORD, auth_header, signup_and_verify, vault_user


def test_setup_returns_recovery_key_and_leaves_vault_unlocked(client, outbox):
    headers, recovery_key = vault_user(client, outbox)
    assert len(recovery_key.replace("-", "")) == 26
    status = client.get("/api/vault/status", headers=headers).json()
    assert status["set_up"] and status["unlocked"]
    assert status["idle_timeout_seconds"] == config.VAULT_IDLE_MINUTES * 60


def test_database_holds_only_wrapped_keys_never_the_master_key(client, outbox):
    vault_user(client, outbox)
    with SessionLocal() as db:
        user = db.scalar(select(User))
        stored = b"".join(
            [
                user.master_salt,
                user.master_verifier,
                user.wrapped_dek_master,
                user.wrapped_dek_recovery,
            ]
        )
        assert MASTER_KEY.encode() not in stored
        assert len(user.wrapped_dek_master) == 12 + 64 + 16  # nonce | hex DEK | tag, not a raw key


def test_either_key_unwraps_the_same_dek(client, outbox):
    _, recovery_key = vault_user(client, outbox)
    with SessionLocal() as db:
        user = db.scalar(select(User))
        params = KdfParams(user.kdf_time_cost, user.kdf_memory_kib, user.kdf_parallelism)
        kek, _ = crypto.derive_keys(MASTER_KEY, user.master_salt, params)
        rec_kek, _ = crypto.derive_keys(
            crypto.normalize_recovery_key(recovery_key), user.recovery_salt, params
        )
        assert crypto.unwrap_dek(kek, user.wrapped_dek_master) == crypto.unwrap_dek(
            rec_kek, user.wrapped_dek_recovery
        )


def test_setup_twice_is_409(client, outbox):
    headers, _ = vault_user(client, outbox)
    res = client.post("/api/vault/setup", json={"master_key": MASTER_KEY + "x"}, headers=headers)
    assert res.status_code == 409


@pytest.mark.parametrize("bad", ["short", "password1234", STRONG_PASSWORD])
def test_setup_rejects_short_weak_or_account_password(client, outbox, bad):
    headers = auth_header(signup_and_verify(client, outbox))
    res = client.post("/api/vault/setup", json={"master_key": bad}, headers=headers)
    assert res.status_code == 422
    assert res.json()["fields"] == ["master_key"]
    assert bad not in res.text


def test_unlock_before_setup_is_409(client, outbox):
    headers = auth_header(signup_and_verify(client, outbox))
    res = client.post("/api/vault/unlock", json={"master_key": MASTER_KEY}, headers=headers)
    assert res.status_code == 409 and res.json()["error"] == "vault_not_set_up"


def test_lock_then_unlock_round_trip(client, outbox):
    headers, _ = vault_user(client, outbox)
    assert client.post("/api/vault/lock", headers=headers).status_code == 204
    assert client.post("/api/vault/lock", headers=headers).status_code == 204  # idempotent
    assert client.get("/api/vault/status", headers=headers).json()["unlocked"] is False

    res = client.post("/api/vault/unlock", json={"master_key": MASTER_KEY}, headers=headers)
    assert res.status_code == 200 and res.json()["unlocked"] is True
    assert client.get("/api/vault/status", headers=headers).json()["unlocked"] is True


def test_wrong_master_key_is_400_with_attempts_counting_down(client, outbox):
    headers, _ = vault_user(client, outbox)
    client.post("/api/vault/lock", headers=headers)
    for expected_left in range(config.MAX_FAILED_ATTEMPTS - 1, 0, -1):
        res = client.post("/api/vault/unlock", json={"master_key": "wrong-key"}, headers=headers)
        assert res.status_code == 400  # 400, not 401: the session itself is fine
        assert res.json() == {
            "error": "invalid_master_key",
            "message": "Wrong master key.",
            "attempts_left": expected_left,
        }


def test_unlock_locks_out_after_five_failures_even_for_the_right_key(client, outbox):
    headers, _ = vault_user(client, outbox)
    client.post("/api/vault/lock", headers=headers)
    for _ in range(config.MAX_FAILED_ATTEMPTS - 1):
        client.post("/api/vault/unlock", json={"master_key": "wrong-key"}, headers=headers)
    last = client.post("/api/vault/unlock", json={"master_key": "wrong-key"}, headers=headers)
    assert last.status_code == 429 and int(last.headers["retry-after"]) > 0

    right = client.post("/api/vault/unlock", json={"master_key": MASTER_KEY}, headers=headers)
    assert right.status_code == 429
    status = client.get("/api/vault/status", headers=headers).json()
    assert status["unlock_locked_until"].endswith("Z")
    with SessionLocal() as db:
        types = {e.type for e in db.scalars(select(SecurityEvent))}
        assert {"unlock_failed", "unlock_locked"} <= types


def test_tampered_wrapped_key_is_409_integrity_failed_not_a_crash(client, outbox):
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
    with SessionLocal() as db:
        assert db.scalar(select(SecurityEvent).where(SecurityEvent.type == "tamper_detected"))


def test_unlock_success_resets_the_failure_counter(client, outbox):
    headers, _ = vault_user(client, outbox)
    client.post("/api/vault/lock", headers=headers)
    client.post("/api/vault/unlock", json={"master_key": "wrong-key"}, headers=headers)
    client.post("/api/vault/unlock", json={"master_key": MASTER_KEY}, headers=headers)
    res = client.post("/api/vault/unlock", json={"master_key": "wrong-key"}, headers=headers)
    assert res.json()["attempts_left"] == config.MAX_FAILED_ATTEMPTS - 1
