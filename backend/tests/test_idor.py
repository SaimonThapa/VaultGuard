"""Demo 3: IDOR (OWASP A01). Knowing another user's real entry id gets you nothing."""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Entry

from .conftest import new_entry, vault_user


def two_users(client, outbox):
    alice, _ = vault_user(client, outbox, "alice")
    bob_client = TestClient(app)  # separate cookie jar: a different browser
    bob, _ = vault_user(bob_client, outbox, "bob")
    return alice, bob, bob_client


def snapshot(entry_id):
    with SessionLocal() as db:
        row = db.get(Entry, entry_id)
        return (
            None if row is None else {c.name: getattr(row, c.name) for c in Entry.__table__.columns}
        )


def test_alice_cannot_read_update_or_delete_bobs_entry(client, outbox):
    alice, bob, bob_client = two_users(client, outbox)
    victim = new_entry(bob_client, bob, site_name="Bobs bank", password="bob-secret-pw").json()
    before = snapshot(victim["id"])
    url = f"/api/entries/{victim['id']}"
    body = {"site_name": "pwned", "password": "attacker-pw"}

    assert client.get(url, headers=alice).status_code == 404
    assert client.put(url, json=body, headers=alice).status_code == 404
    assert client.delete(url, headers=alice).status_code == 404

    assert snapshot(victim["id"]) == before  # bob's row is byte-for-byte unchanged
    assert bob_client.get(url, headers=bob).json()["password"] == "bob-secret-pw"


def test_foreign_id_looks_exactly_like_a_missing_id(client, outbox):
    alice, bob, bob_client = two_users(client, outbox)
    victim = new_entry(bob_client, bob).json()
    foreign = client.get(f"/api/entries/{victim['id']}", headers=alice)
    missing = client.get(f"/api/entries/{uuid.uuid4()}", headers=alice)
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json()  # no existence leak


def test_lists_and_search_never_include_other_users_entries(client, outbox):
    alice, bob, bob_client = two_users(client, outbox)
    new_entry(client, alice, site_name="Alice mail")
    new_entry(bob_client, bob, site_name="Bobs bank")

    assert [
        e["site_name"] for e in client.get("/api/entries", headers=alice).json()["entries"]
    ] == ["Alice mail"]
    found = client.get("/api/entries", params={"q": "bank"}, headers=alice).json()
    assert found["entries"] == []


def test_deleting_a_user_never_touches_other_rows(client, outbox):
    alice, bob, bob_client = two_users(client, outbox)
    new_entry(client, alice)
    victim = new_entry(bob_client, bob).json()
    with SessionLocal() as db:
        assert len(db.scalars(select(Entry)).all()) == 2
    client.delete(f"/api/entries/{victim['id']}", headers=alice)
    with SessionLocal() as db:
        assert len(db.scalars(select(Entry)).all()) == 2
