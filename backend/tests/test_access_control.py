"""Demo 2: broken access control (OWASP A01). No token, bad token or locked vault is refused."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app import config
from app.core import key_store
from app.main import app

from .conftest import new_entry, signup_and_verify, vault_user

# The only routes allowed without an access token. Anything else must answer 401.
PUBLIC = {
    ("GET", "/api/health"),
    ("POST", "/api/auth/signup"),
    ("POST", "/api/auth/verify-email"),
    ("POST", "/api/auth/resend-verification"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/refresh"),  # cookie only: answers 401 without one
    ("POST", "/api/auth/logout"),
    ("POST", "/api/auth/forgot-password"),
    ("POST", "/api/auth/reset-password"),
}


def api_routes():
    """Every (method, path) the app serves, read from its OpenAPI schema (docs stay off)."""
    for path, operations in app.openapi()["paths"].items():
        for method in operations:
            yield method.upper(), path


def test_every_non_public_route_refuses_a_missing_token(client):
    checked = []
    for method, template in api_routes():
        if (method, template) in PUBLIC:
            continue
        path = template.replace("{entry_id}", str(uuid.uuid4()))
        res = client.request(method, path, json={} if method in ("POST", "PUT") else None)
        assert res.status_code == 401, f"{method} {path} answered {res.status_code} without a token"
        checked.append((method, path))
    assert len(checked) >= 8  # entries (5) + vault (4) at the time of writing; new routes join in


def forged(**overrides):
    claims = {
        "sub": "1",
        "sid": "x",
        "type": "access",
        "exp": datetime.now(UTC) + timedelta(minutes=5),
        **overrides,
    }
    return claims


@pytest.mark.parametrize(
    "token",
    [
        "garbage",
        jwt.encode(forged(), "not-the-real-secret-not-the-real-secret", algorithm="HS256"),
        jwt.encode(forged(), "", algorithm="none"),  # alg=none attack
        jwt.encode(
            forged(exp=datetime.now(UTC) - timedelta(minutes=1)), config.JWT_SECRET, "HS256"
        ),
        jwt.encode(forged(type="refresh"), config.JWT_SECRET, "HS256"),
    ],
    ids=["garbage", "wrong-secret", "alg-none", "expired", "wrong-type"],
)
def test_bad_tokens_are_401(client, token):
    res = client.get("/api/vault/status", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401 and res.json()["error"] == "unauthorized"


def test_valid_signature_but_revoked_session_is_401(client, outbox):
    headers, _ = vault_user(client, outbox)
    assert client.get("/api/vault/status", headers=headers).status_code == 200
    client.post("/api/auth/logout")
    assert client.get("/api/vault/status", headers=headers).status_code == 401


def test_unlocked_routes_answer_423_while_the_vault_is_locked(client, outbox):
    headers, _ = vault_user(client, outbox)
    entry = new_entry(client, headers).json()
    client.post("/api/vault/lock", headers=headers)
    body = {"site_name": "x", "password": "y"}
    eid = entry["id"]
    for method, path, payload in [
        ("POST", "/api/entries", body),
        ("GET", f"/api/entries/{eid}", None),
        ("PUT", f"/api/entries/{eid}", body),
        ("DELETE", f"/api/entries/{eid}", None),
    ]:
        res = client.request(method, path, json=payload, headers=headers)
        assert res.status_code == 423, f"{method} {path}"
        assert res.json()["error"] == "vault_locked"


def test_vault_relocks_after_the_idle_timeout(client, outbox, monkeypatch):
    headers, _ = vault_user(client, outbox)
    assert new_entry(client, headers).status_code == 201
    monkeypatch.setattr(key_store, "VAULT_IDLE_MINUTES", -1)  # everything counts as idle
    assert new_entry(client, headers).status_code == 423
    assert client.get("/api/vault/status", headers=headers).json()["unlocked"] is False


def test_unverified_account_cannot_use_a_token(client, outbox):
    client.post(
        "/api/auth/signup",
        json={"username": "eve", "email": "eve@demo.mail", "password": "Tr0ub4dor&3-horse-staple"},
    )
    assert client.get("/api/vault/status").status_code == 401


def test_logged_in_but_vault_not_set_up_is_locked_not_a_crash(client, outbox):
    headers = {"Authorization": f"Bearer {signup_and_verify(client, outbox)['access_token']}"}
    assert client.get("/api/entries", headers=headers).json() == {"locked": True, "entries": []}
    assert new_entry(client, headers).status_code == 423
