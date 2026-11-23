"""Demo 4: SQL injection (OWASP A05). Input is always data, never SQL."""

import pytest
from sqlalchemy import inspect

from app.db import engine

from .conftest import new_entry, vault_user

PAYLOADS = ["' OR 1=1 --", "'; DROP TABLE entries;--", '" OR ""="', "1; SELECT * FROM users"]


def search(client, headers, q):
    res = client.get("/api/entries", params={"q": q}, headers=headers)
    assert res.status_code == 200
    return [e["site_name"] for e in res.json()["entries"]]


@pytest.fixture
def seeded(client, outbox):
    headers, _ = vault_user(client, outbox)
    for name in ("GitHub", "100% Legit", "under_score", "back\\slash"):
        new_entry(client, headers, site_name=name)
    return headers


@pytest.mark.parametrize("payload", PAYLOADS)
def test_injection_in_search_returns_nothing_and_keeps_the_table(client, seeded, payload):
    assert search(client, seeded, payload) == []
    assert "entries" in inspect(engine).get_table_names()
    assert len(search(client, seeded, "")) == 4  # nothing was dropped or altered


def test_like_wildcards_are_literal(client, seeded):
    assert search(client, seeded, "%") == ["100% Legit"]
    assert search(client, seeded, "_") == ["under_score"]
    assert search(client, seeded, "\\") == ["back\\slash"]


def test_an_entry_named_like_an_attack_is_found_only_by_its_exact_text(client, outbox):
    headers, _ = vault_user(client, outbox)
    new_entry(client, headers, site_name="' OR 1=1 --")
    new_entry(client, headers, site_name="Normal")
    assert search(client, headers, "' OR 1=1 --") == ["' OR 1=1 --"]


@pytest.mark.parametrize("payload", ["' OR '1'='1", "admin'--", "' OR 1=1 --", "alice' OR 1=1 --"])
def test_injection_as_username_at_login_is_just_a_failed_login(client, outbox, payload):
    vault_user(client, outbox)
    res = client.post("/api/auth/login", json={"username": payload, "password": "anything-at-all"})
    assert res.status_code == 401
    assert res.json()["error"] == "invalid_credentials"


def test_injection_as_password_at_login_is_just_a_failed_login(client, outbox):
    vault_user(client, outbox)
    res = client.post("/api/auth/login", json={"username": "alice", "password": "' OR '1'='1"})
    assert res.status_code == 401
