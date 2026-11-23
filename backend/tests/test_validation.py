"""Every product_backend.md §4 rule rejects bad input with 422, without echoing the value."""

import uuid

import pytest

from .conftest import new_entry, vault_user

GOOD = {"site_name": "Site", "password": "pw"}


@pytest.fixture
def headers(client, outbox):
    return vault_user(client, outbox)[0]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("site_name", ""),
        ("site_name", "   "),
        ("site_name", "x" * 101),
        ("site_url", "ftp://example.com"),
        ("site_url", "javascript:alert(1)"),
        ("site_url", "https://"),
        ("site_url", "x" * 2049),
        ("username", "u" * 257),
        ("password", ""),
        ("password", "p" * 257),
        ("notes", "n" * 2001),
        ("rotation_days", 0),
        ("rotation_days", 3651),
        ("rotation_days", "soon"),
    ],
)
def test_entry_rules(client, headers, field, value):
    res = client.post("/api/entries", json={**GOOD, field: value}, headers=headers)
    assert res.status_code == 422
    assert res.json()["error"] == "validation_error"
    assert field in res.json()["fields"]
    assert "javascript:alert" not in res.text and "ftp://" not in res.text


@pytest.mark.parametrize(
    "body",
    [{"site_name": "ok", "password": "pw", "role": "admin"}, {"site_name": "ok"}, {}],
    ids=["unknown-field", "missing-password", "empty"],
)
def test_unknown_or_missing_fields_are_rejected(client, headers, body):
    assert client.post("/api/entries", json=body, headers=headers).status_code == 422


def test_boundary_values_are_accepted(client, headers):
    res = new_entry(
        client,
        headers,
        site_name="x" * 100,
        username="u" * 256,
        password="p" * 256,
        notes="n" * 2000,
        rotation_days=3650,
        site_url="youtube.com",
    )
    assert res.status_code == 201
    assert res.json()["site_url"] == "https://youtube.com"


def test_empty_username_and_notes_are_allowed(client, headers):
    res = client.post("/api/entries", json=GOOD, headers=headers)
    assert res.status_code == 201
    assert res.json()["username"] == "" and res.json()["notes"] is None


def test_entry_id_must_be_a_uuid(client, headers):
    assert client.get("/api/entries/not-a-uuid", headers=headers).status_code == 422
    assert client.get(f"/api/entries/{uuid.uuid4()}", headers=headers).status_code == 404


def test_search_query_length_is_capped(client, headers):
    assert client.get("/api/entries", params={"q": "q" * 101}, headers=headers).status_code == 422
    assert client.get("/api/entries", params={"q": "q" * 100}, headers=headers).status_code == 200


def test_malformed_json_is_a_clean_422_not_a_500(client, headers):
    res = client.post(
        "/api/entries",
        content=b"{not json",
        headers={**headers, "Content-Type": "application/json"},
    )
    assert res.status_code == 422
    assert res.json()["error"] == "validation_error"
