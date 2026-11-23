import pytest

from app.core import crypto, key_store, tokens
from app.core.crypto import IntegrityError, KdfParams

FAST = KdfParams(time_cost=1, memory_kib=64, parallelism=1)


def test_encrypt_decrypt_round_trip():
    key = crypto.new_dek()
    blob = crypto.encrypt(key, "hunter2 ✓", "1|abc|password")
    assert crypto.decrypt(key, blob, "1|abc|password") == "hunter2 ✓"
    assert b"hunter2" not in blob


def test_wrong_key_fails():
    blob = crypto.encrypt(crypto.new_dek(), "secret", "aad")
    with pytest.raises(IntegrityError):
        crypto.decrypt(crypto.new_dek(), blob, "aad")


def test_flipped_byte_fails():
    key = crypto.new_dek()
    blob = bytearray(crypto.encrypt(key, "secret", "aad"))
    blob[15] ^= 1
    with pytest.raises(IntegrityError):
        crypto.decrypt(key, bytes(blob), "aad")


@pytest.mark.parametrize("other", ["2|abc|password", "1|xyz|password", "1|abc|username"])
def test_swapped_aad_fails(other):
    key = crypto.new_dek()
    blob = crypto.encrypt(key, "secret", crypto.field_aad(1, "abc", "password"))
    with pytest.raises(IntegrityError):
        crypto.decrypt(key, blob, other)


def test_nonces_are_unique():
    key = crypto.new_dek()
    assert crypto.encrypt(key, "x", "a") != crypto.encrypt(key, "x", "a")


def test_truncated_blob_is_integrity_error_not_crash():
    with pytest.raises(IntegrityError):
        crypto.decrypt(crypto.new_dek(), b"short", "aad")


def test_derive_keys_is_deterministic_and_split():
    salt = crypto.new_salt()
    kek, verifier = crypto.derive_keys("correct horse battery", salt, FAST)
    assert (kek, verifier) == crypto.derive_keys("correct horse battery", salt, FAST)
    assert kek != verifier
    assert crypto.derive_keys("other", salt, FAST)[0] != kek


def test_wrap_unwrap_dek():
    dek = crypto.new_dek()
    kek, _ = crypto.derive_keys("master key phrase", crypto.new_salt(), FAST)
    assert crypto.unwrap_dek(kek, crypto.wrap_dek(kek, dek)) == dek
    other_kek, _ = crypto.derive_keys("different", crypto.new_salt(), FAST)
    with pytest.raises(IntegrityError):
        crypto.unwrap_dek(other_kek, crypto.wrap_dek(kek, dek))


def test_recovery_key_format_and_normalizing():
    key = crypto.new_recovery_key()
    groups = key.split("-")
    assert [len(g) for g in groups] == [4, 4, 4, 4, 4, 4, 2]
    assert all(c in crypto.CROCKFORD for c in key.replace("-", ""))
    assert crypto.normalize_recovery_key(key.lower()) == key.replace("-", "")
    assert crypto.normalize_recovery_key("too-short") is None


def test_access_token_round_trip_and_rejections():
    token = tokens.create_access_token(7, "sid1")
    assert tokens.decode_access_token(token) == (7, "sid1")
    assert tokens.decode_access_token(token + "x") is None
    assert tokens.decode_access_token("not.a.jwt") is None


def test_alg_none_token_is_rejected():
    import jwt

    forged = jwt.encode({"sub": "1", "sid": "s", "type": "access", "exp": 9999999999}, "", "none")
    assert tokens.decode_access_token(forged) is None


def test_key_store_lock_and_idle_expiry(monkeypatch):
    key_store.clear()
    key_store.put("s1", 1, b"k" * 32)
    assert key_store.get("s1").dek == b"k" * 32
    key_store.drop("s1")
    assert key_store.get("s1") is None

    key_store.put("s2", 1, b"k" * 32)
    monkeypatch.setattr(key_store, "VAULT_IDLE_MINUTES", -1)  # everything is already idle
    assert key_store.get("s2") is None
    assert not key_store.is_unlocked("s2")


def test_drop_user_keeps_requested_session():
    key_store.clear()
    key_store.put("a", 1, b"1" * 32)
    key_store.put("b", 1, b"1" * 32)
    key_store.put("c", 2, b"2" * 32)
    key_store.drop_user(1, except_session="a")
    assert key_store.is_unlocked("a")
    assert not key_store.is_unlocked("b")
    assert key_store.is_unlocked("c")
    key_store.clear()
