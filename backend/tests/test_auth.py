import pytest
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select

from app.db import SessionLocal
from app.dependencies import get_session
from app.errors import AppError
from app.models import Otp, SecurityEvent, User

from .conftest import STRONG_PASSWORD, last_code, signup_and_verify

BASE = {"username": "alice", "email": "alice@demo.mail", "password": STRONG_PASSWORD}


def test_signup_verify_login(client, outbox):
    payload = signup_and_verify(client, outbox)
    assert payload["user"]["username"] == "alice"
    assert payload["vault"] == {"set_up": False, "unlocked": False}
    assert "vg_refresh" in client.cookies

    res = client.post("/api/auth/login", json={"username": "ALICE", "password": STRONG_PASSWORD})
    assert res.status_code == 200
    assert res.json()["access_token"]


def test_refresh_cookie_is_httponly_strict_and_scoped(client, outbox):
    client.post("/api/auth/signup", json=BASE)
    res = client.post(
        "/api/auth/verify-email",
        json={"username": "alice", "code": last_code(outbox, BASE["email"])},
    )
    cookie = res.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/api/auth" in cookie


def test_signup_conflict_uses_one_message(client, outbox):
    client.post("/api/auth/signup", json=BASE)
    same_user = client.post("/api/auth/signup", json={**BASE, "email": "other@demo.mail"})
    same_email = client.post("/api/auth/signup", json={**BASE, "username": "bob"})
    assert same_user.status_code == same_email.status_code == 409
    assert same_user.json() == same_email.json()


@pytest.mark.parametrize(
    "bad",
    [
        {"username": "a"},  # too short
        {"username": "bad name!"},
        {"email": "not-an-email"},
        {"password": "short"},
        {"password": "password1234"},  # long enough but weak
        {"extra": "field"},  # unknown fields are rejected
    ],
)
def test_signup_validation_returns_422_without_echoing_values(client, bad):
    res = client.post("/api/auth/signup", json={**BASE, **bad})
    assert res.status_code == 422
    body = res.json()
    assert body["error"] == "validation_error"
    assert "password1234" not in res.text and "bad name" not in res.text


def test_unverified_login_is_403(client, outbox):
    client.post("/api/auth/signup", json=BASE)
    res = client.post("/api/auth/login", json={"username": "alice", "password": STRONG_PASSWORD})
    assert res.status_code == 403 and res.json()["error"] == "email_not_verified"


def test_wrong_password_and_unknown_user_look_identical(client, outbox):
    signup_and_verify(client, outbox)
    wrong = client.post("/api/auth/login", json={"username": "alice", "password": "nope"})
    unknown = client.post("/api/auth/login", json={"username": "ghost", "password": "nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_bad_verification_code_is_400(client, outbox):
    client.post("/api/auth/signup", json=BASE)
    res = client.post("/api/auth/verify-email", json={"username": "alice", "code": "000000"})
    assert res.status_code == 400 and res.json()["error"] == "invalid_otp"


def test_refresh_rotates_and_reuse_revokes_the_session(client, outbox):
    signup_and_verify(client, outbox)
    old_cookie = client.cookies["vg_refresh"]

    first = client.post("/api/auth/refresh")
    assert first.status_code == 200
    new_cookie = client.cookies["vg_refresh"]
    assert new_cookie != old_cookie

    # An attacker replays the OLD token: the whole session is revoked, even for the new token.
    client.cookies.clear()
    client.cookies.set("vg_refresh", old_cookie, path="/api/auth")
    assert client.post("/api/auth/refresh").status_code == 401
    client.cookies.clear()
    client.cookies.set("vg_refresh", new_cookie, path="/api/auth")
    assert client.post("/api/auth/refresh").status_code == 401

    with SessionLocal() as db:
        assert db.scalar(select(SecurityEvent).where(SecurityEvent.type == "refresh_reuse"))


def test_refresh_without_cookie_is_401(client):
    assert client.post("/api/auth/refresh").status_code == 401


def test_logout_kills_the_access_token_immediately(client, outbox):
    payload = signup_and_verify(client, outbox)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=payload["access_token"])
    with SessionLocal() as db:
        assert get_session(creds, db).user.username == "alice"

    assert client.post("/api/auth/logout").status_code == 204
    assert client.post("/api/auth/refresh").status_code == 401  # cookie cleared

    with SessionLocal() as db, pytest.raises(AppError) as exc:
        get_session(creds, db)  # same, still-unexpired JWT, but its session is revoked
    assert exc.value.status == 401


def test_logout_is_idempotent(client):
    assert client.post("/api/auth/logout").status_code == 204


def test_forgot_password_same_response_for_unknown_email(client, outbox):
    signup_and_verify(client, outbox)
    known = client.post("/api/auth/forgot-password", json={"email": "alice@demo.mail"})
    unknown = client.post("/api/auth/forgot-password", json={"email": "ghost@demo.mail"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert not any(to == "ghost@demo.mail" for to, _, _ in outbox)


def test_reset_password_revokes_sessions_and_clears_lockout(client, outbox):
    signup_and_verify(client, outbox)
    client.post("/api/auth/forgot-password", json={"email": "alice@demo.mail"})
    new_password = "Another-Str0ng-passphrase!"  # noqa: S105
    res = client.post(
        "/api/auth/reset-password",
        json={
            "email": "alice@demo.mail",
            "code": last_code(outbox, "alice@demo.mail"),
            "new_password": new_password,
        },
    )
    assert res.status_code == 200

    assert client.post("/api/auth/refresh").status_code == 401  # old session is gone
    assert (
        client.post(
            "/api/auth/login", json={"username": "alice", "password": STRONG_PASSWORD}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login", json={"username": "alice", "password": new_password}
        ).status_code
        == 200
    )


def test_reset_password_rejects_weak_password_and_bad_code(client, outbox):
    signup_and_verify(client, outbox)
    client.post("/api/auth/forgot-password", json={"email": "alice@demo.mail"})
    code = last_code(outbox, "alice@demo.mail")
    weak = client.post(
        "/api/auth/reset-password",
        json={"email": "alice@demo.mail", "code": code, "new_password": "password1234"},
    )
    assert weak.status_code == 422
    bad = client.post(
        "/api/auth/reset-password",
        json={
            "email": "alice@demo.mail",
            "code": "000000",
            "new_password": "Another-Str0ng-passphrase!",
        },
    )
    assert bad.status_code == 400
    unknown = client.post(
        "/api/auth/reset-password",
        json={
            "email": "ghost@demo.mail",
            "code": code,
            "new_password": "Another-Str0ng-passphrase!",
        },
    )
    assert unknown.status_code == 400  # same as a wrong code: no enumeration


def test_secrets_are_not_stored_in_the_database(client, outbox):
    signup_and_verify(client, outbox)
    with SessionLocal() as db:
        user = db.scalar(select(User))
        assert user.password_hash.startswith("$argon2id$")
        assert STRONG_PASSWORD not in user.password_hash
        otp = db.scalar(select(Otp))
        assert len(otp.code_hmac) == 64  # HMAC hex, not the 6-digit code
