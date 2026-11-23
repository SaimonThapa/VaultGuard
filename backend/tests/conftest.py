"""Test environment. Runs before any app module is imported, so config sees these values.

Argon2 parameters are lowered for the test suite only (keeps it fast); production defaults are
untouched. HIBP is off so tests never touch the network.
"""

import os
import re
import tempfile

_tmp = tempfile.mkdtemp(prefix="vaultguard-test-")
os.environ.update(
    {
        "DATABASE_URL": f"sqlite:///{_tmp}/test.db",
        "JWT_SECRET": "test-jwt-secret-0123456789-abcdefghijklmnopqrstuvwxyz",
        "OTP_PEPPER": "test-otp-pepper-0123456789-abcdefghijklmnopqrstuvwxyz",
        "ARGON2_TIME_COST": "1",
        "ARGON2_MEMORY_KIB": "64",
        "ARGON2_PARALLELISM": "1",
        "HIBP_ENABLED": "false",
        "DEBUG": "false",
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core import key_store  # noqa: E402
from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services import email  # noqa: E402

STRONG_PASSWORD = "Tr0ub4dor&3-horse-staple"


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    """Empty tables, empty key store and a captured outbox for every test."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    key_store.clear()
    outbox: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        email, "send_email", lambda to, subject, body: outbox.append((to, subject, body))
    )
    return outbox


@pytest.fixture
def outbox(fresh_state):
    return fresh_state


@pytest.fixture
def client():
    return TestClient(app)


def last_code(outbox, to: str) -> str:
    """The most recent 6-digit code emailed to an address."""
    bodies = [body for (rcpt, _subject, body) in outbox if rcpt == to]
    return re.search(r": (\d{6})\n", bodies[-1]).group(1)


def signup_and_verify(client, outbox, username="alice", email_addr="alice@demo.mail"):
    """Create a verified, logged-in account. Returns the verify-email response JSON."""
    res = client.post(
        "/api/auth/signup",
        json={"username": username, "email": email_addr, "password": STRONG_PASSWORD},
    )
    assert res.status_code == 201, res.text
    res = client.post(
        "/api/auth/verify-email",
        json={"username": username, "code": last_code(outbox, email_addr)},
    )
    assert res.status_code == 200, res.text
    return res.json()


def auth_header(payload) -> dict:
    return {"Authorization": f"Bearer {payload['access_token']}"}


MASTER_KEY = "7K3Q-9XWM-2PDA-H8RT-Y4NC-6VBE-1Z"


def vault_user(client, outbox, username="alice", email_addr=None):
    """A verified user with a set-up, unlocked vault. Returns (auth headers, recovery key)."""
    payload = signup_and_verify(client, outbox, username, email_addr or f"{username}@demo.mail")
    headers = auth_header(payload)
    res = client.post("/api/vault/setup", json={"master_key": MASTER_KEY}, headers=headers)
    assert res.status_code == 201, res.text
    return headers, res.json()["recovery_key"]


def new_entry(client, headers, **overrides):
    body = {
        "site_name": "GitHub",
        "site_url": "github.com",
        "username": "alice-dev",
        "password": "S3cret!pass-one",
        "notes": None,
        "rotation_days": None,
    }
    return client.post("/api/entries", json={**body, **overrides}, headers=headers)
