from datetime import timedelta

from sqlalchemy import select

from app import config
from app.db import SessionLocal, utcnow
from app.models import Otp, SecurityEvent

from .conftest import STRONG_PASSWORD, last_code, signup_and_verify


def bad_login(client, username="alice"):
    return client.post("/api/auth/login", json={"username": username, "password": "wrong-password"})


def test_five_bad_logins_lock_the_account_with_retry_after(client, outbox):
    signup_and_verify(client, outbox)
    for _ in range(config.MAX_FAILED_ATTEMPTS - 1):
        assert bad_login(client).status_code == 401
    locked = bad_login(client)
    assert locked.status_code == 429
    assert locked.json()["error"] == "too_many_attempts"
    assert 1 <= int(locked.headers["retry-after"]) <= config.LOCKOUT_MINUTES * 60


def test_correct_password_is_refused_while_locked(client, outbox):
    signup_and_verify(client, outbox)
    for _ in range(config.MAX_FAILED_ATTEMPTS):
        bad_login(client)
    res = client.post("/api/auth/login", json={"username": "alice", "password": STRONG_PASSWORD})
    assert res.status_code == 429


def test_lock_expires_and_success_resets_the_counter(client, outbox):
    signup_and_verify(client, outbox)
    for _ in range(config.MAX_FAILED_ATTEMPTS):
        bad_login(client)
    from app.models import User

    with SessionLocal() as db:
        user = db.scalar(select(User))
        user.login_locked_until = utcnow() - timedelta(seconds=1)
        db.commit()
    assert (
        client.post(
            "/api/auth/login", json={"username": "alice", "password": STRONG_PASSWORD}
        ).status_code
        == 200
    )
    with SessionLocal() as db:
        assert db.scalar(select(User)).failed_login_count == 0
        types = {e.type for e in db.scalars(select(SecurityEvent))}
        assert {"login_failed", "login_locked", "login_ok"} <= types


def test_failures_are_consecutive_not_cumulative(client, outbox):
    signup_and_verify(client, outbox)
    for _ in range(config.MAX_FAILED_ATTEMPTS - 1):
        bad_login(client)
    assert (
        client.post(
            "/api/auth/login", json={"username": "alice", "password": STRONG_PASSWORD}
        ).status_code
        == 200
    )
    assert bad_login(client).status_code == 401  # counter restarted, not 429


def test_otp_dies_after_max_attempts_even_with_the_right_code(client, outbox):
    client.post(
        "/api/auth/signup",
        json={"username": "alice", "email": "alice@demo.mail", "password": STRONG_PASSWORD},
    )
    code = last_code(outbox, "alice@demo.mail")
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(config.OTP_MAX_ATTEMPTS):
        res = client.post("/api/auth/verify-email", json={"username": "alice", "code": wrong})
        assert res.status_code == 400
    res = client.post("/api/auth/verify-email", json={"username": "alice", "code": code})
    assert res.status_code == 400


def test_expired_otp_is_rejected(client, outbox):
    client.post(
        "/api/auth/signup",
        json={"username": "alice", "email": "alice@demo.mail", "password": STRONG_PASSWORD},
    )
    with SessionLocal() as db:
        otp = db.scalar(select(Otp))
        otp.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    res = client.post(
        "/api/auth/verify-email",
        json={"username": "alice", "code": last_code(outbox, "alice@demo.mail")},
    )
    assert res.status_code == 400


def test_resend_cooldown_sends_nothing_and_still_answers_202(client, outbox):
    client.post(
        "/api/auth/signup",
        json={"username": "alice", "email": "alice@demo.mail", "password": STRONG_PASSWORD},
    )
    before = len(outbox)
    res = client.post("/api/auth/resend-verification", json={"username": "alice"})
    assert res.status_code == 202
    assert len(outbox) == before  # inside the 60 s cooldown


def test_resend_after_cooldown_invalidates_the_old_code(client, outbox):
    client.post(
        "/api/auth/signup",
        json={"username": "alice", "email": "alice@demo.mail", "password": STRONG_PASSWORD},
    )
    old = last_code(outbox, "alice@demo.mail")
    with SessionLocal() as db:
        otp = db.scalar(select(Otp))
        otp.created_at = utcnow() - timedelta(seconds=config.OTP_RESEND_SECONDS + 1)
        db.commit()
    client.post("/api/auth/resend-verification", json={"username": "alice"})
    new = last_code(outbox, "alice@demo.mail")
    if new != old:  # (1 in a million collision)
        res = client.post("/api/auth/verify-email", json={"username": "alice", "code": old})
        assert res.status_code == 400
    assert (
        client.post("/api/auth/verify-email", json={"username": "alice", "code": new}).status_code
        == 200
    )
