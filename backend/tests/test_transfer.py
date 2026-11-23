import json

from fastapi.testclient import TestClient
from sqlalchemy import select

from app import config
from app.controllers import transfer
from app.db import SessionLocal
from app.main import app
from app.models import SecurityEvent

from .conftest import MASTER_KEY, auth_header, new_entry, signup_and_verify, vault_user

CHROME_HEADER = "name,url,username,password,note\n"
BOB_KEY = "Bobs-Very-Own-Master-Key-2026!"


def upload(client, headers, content, filename="chrome.csv", master_key=None):
    if isinstance(content, str):
        content = content.encode()
    data = {"master_key": master_key} if master_key else None
    return client.post(
        "/api/import", files={"file": (filename, content)}, data=data, headers=headers
    )


def entries(client, headers):
    return client.get("/api/entries", headers=headers).json()["entries"]


# --- Chrome CSV ---


def test_chrome_csv_import(client, outbox):
    headers, _ = vault_user(client, outbox)
    csv_text = (
        CHROME_HEADER
        + "GitHub,https://github.com/login,alice,Gh-Secret!2026-xyz,work account\n"
        + ",https://news.example.org/path,alice,Zq-Another-Pw-77,\n"  # empty name -> host
    )
    res = upload(client, headers, csv_text)
    assert res.status_code == 200
    assert res.json() == {"imported": 2, "skipped_duplicates": 0, "failed_rows": []}
    by_name = {e["site_name"]: e for e in entries(client, headers)}
    assert by_name["GitHub"]["notes"] == "work account"
    assert "news.example.org" in by_name  # falls back to the URL's host
    with SessionLocal() as db:
        assert db.scalar(select(SecurityEvent).where(SecurityEvent.type == "import"))


def test_exact_duplicates_are_skipped_against_the_vault_and_within_the_file(client, outbox):
    headers, _ = vault_user(client, outbox)
    new_entry(
        client,
        headers,
        site_name="GitHub",
        site_url="https://github.com",
        username="u",
        password="pw-1",
    )
    row = "GitHub,https://github.com,u,pw-1,\n"
    other = "GitHub,https://github.com,u,pw-2,\n"  # same site, different password: kept
    res = upload(client, headers, CHROME_HEADER + row + other + other).json()
    assert res["imported"] == 1 and res["skipped_duplicates"] == 2
    assert len(entries(client, headers)) == 2  # redundancy across different credentials is allowed


def test_bad_rows_are_reported_by_row_and_field_never_by_value(client, outbox):
    headers, _ = vault_user(client, outbox)
    csv_text = (
        CHROME_HEADER
        + "Good,https://good.example,u,pw-good-1,\n"
        + "Bad URL,ftp://evil.example,u,SECRET-PW-IN-BAD-ROW,\n"
        + "No password,https://x.example,u,,\n"
    )
    res = upload(client, headers, csv_text)
    body = res.json()
    assert body["imported"] == 1
    assert body["failed_rows"] == [
        {"row": 3, "reason": "site_url"},
        {"row": 4, "reason": "password"},
    ]
    assert "SECRET-PW-IN-BAD-ROW" not in res.text and "evil.example" not in res.text


def test_import_is_all_or_nothing_per_structural_error(client, outbox):
    headers, _ = vault_user(client, outbox)
    for content in [
        "just,some,words\n1,2,3\n",
        "",
        "not a csv or json at all \x00\x01",
        "name,url\nx,y\n",
    ]:
        res = upload(client, headers, content)
        assert res.status_code == 400, content
        assert res.json()["error"] == "invalid_import"
    assert entries(client, headers) == []


def test_oversized_and_too_many_rows_are_rejected(client, outbox):
    headers, _ = vault_user(client, outbox)
    big = CHROME_HEADER + "a,https://a.example,u,pw,x\n" * 50_000
    assert len(big) > transfer.MAX_BYTES
    assert upload(client, headers, big).status_code == 400
    many = CHROME_HEADER + "".join(f"s{i},,u{i},pw{i},\n" for i in range(transfer.MAX_ROWS + 1))
    assert len(many) < transfer.MAX_BYTES
    assert upload(client, headers, many).status_code == 400
    assert entries(client, headers) == []


def test_csv_with_a_bom_and_extra_columns_imports(client, outbox):
    headers, _ = vault_user(client, outbox)
    content = "﻿name,url,username,password,note,extra\nSite,https://s.example,u,pw-1,,whatever\n"
    assert upload(client, headers, content).json()["imported"] == 1


def test_import_needs_an_unlocked_vault(client, outbox):
    headers, _ = vault_user(client, outbox)
    client.post("/api/vault/lock", headers=headers)
    assert upload(client, headers, CHROME_HEADER + "a,,u,pw,\n").status_code == 423


def test_formula_like_values_are_stored_as_plain_text(client, outbox):
    headers, _ = vault_user(client, outbox)
    upload(client, headers, CHROME_HEADER + 'Sheet,,=HYPERLINK("http://x"),pw-1,\n')
    assert entries(client, headers)[0]["username"] == '=HYPERLINK("http://x")'


# --- export ---


def export(client, headers, key=MASTER_KEY):
    return client.post("/api/export", json={"master_key": key}, headers=headers)


def test_export_requires_the_master_key_and_counts_failures(client, outbox):
    headers, _ = vault_user(client, outbox)
    new_entry(client, headers)
    res = export(client, headers, "wrong-key")
    assert res.status_code == 400 and res.json()["attempts_left"] == config.MAX_FAILED_ATTEMPTS - 1
    assert export(client, headers).status_code == 200
    for _ in range(config.MAX_FAILED_ATTEMPTS):
        last = export(client, headers, "wrong-key")
    assert last.status_code == 429  # export's step-up check shares the unlock lockout


def test_export_is_an_attachment_and_fully_encrypted(client, outbox):
    headers, _ = vault_user(client, outbox)
    new_entry(
        client,
        headers,
        site_name="Very Secret Site",
        password="S3cret!pass-one",
        notes="private note",
    )
    res = export(client, headers)
    assert res.status_code == 200
    assert res.headers["content-disposition"].startswith('attachment; filename="vaultguard-backup-')
    for plain in ("Very Secret Site", "S3cret!pass-one", "private note", "alice-dev", "github"):
        assert plain not in res.text  # even site names are encrypted in a backup
    doc = res.json()
    assert doc["format"] == "vaultguard-backup" and doc["version"] == 1 and len(doc["entries"]) == 1
    assert doc["skipped_integrity"] == 0 and doc["kdf"]["alg"] == "argon2id"
    with SessionLocal() as db:
        assert db.scalar(select(SecurityEvent).where(SecurityEvent.type == "export"))


def test_export_leaves_out_tampered_entries_and_says_so(client, outbox):
    headers, _ = vault_user(client, outbox)
    good = new_entry(client, headers, site_name="Good").json()
    bad = new_entry(client, headers, site_name="Bad").json()
    from .test_tamper import flip_byte

    flip_byte(bad["id"])
    doc = export(client, headers).json()
    assert doc["skipped_integrity"] == 1 and [e["id"] for e in doc["entries"]] == [good["id"]]


# --- round trip into another account ---


def second_user(outbox, key=BOB_KEY):
    bob_client = TestClient(app)
    headers = auth_header(signup_and_verify(bob_client, outbox, "bob", "bob@demo.mail"))
    assert (
        bob_client.post("/api/vault/setup", json={"master_key": key}, headers=headers).status_code
        == 201
    )
    return bob_client, headers


def test_export_then_import_round_trips_into_another_account(client, outbox):
    alice, _ = vault_user(client, outbox, "alice")
    new_entry(
        client,
        alice,
        site_name="GitHub",
        site_url="github.com",
        username="a1",
        password="pw-aaa-1",
        notes="n",
        rotation_days=90,
    )
    new_entry(client, alice, site_name="Mail", username="a2", password="pw-bbb-2")
    backup = export(client, alice).content

    bob_client, bob = second_user(outbox)
    res = upload(
        bob_client, bob, backup, "backup.json", master_key=MASTER_KEY
    )  # alice's key opens it
    assert res.status_code == 200 and res.json()["imported"] == 2
    got = {e["site_name"]: e for e in entries(bob_client, bob)}
    assert got["GitHub"]["password"] == "pw-aaa-1" and got["GitHub"]["rotation_days"] == 90
    assert got["GitHub"]["notes"] == "n" and got["Mail"]["username"] == "a2"
    assert got["GitHub"]["id"] not in {e["id"] for e in entries(client, alice)}  # fresh ids

    again = upload(bob_client, bob, backup, "backup.json", master_key=MASTER_KEY).json()
    assert again["imported"] == 0 and again["skipped_duplicates"] == 2


def test_backup_with_the_wrong_or_missing_key_is_400_invalid_master_key(client, outbox):
    alice, _ = vault_user(client, outbox, "alice")
    new_entry(client, alice)
    backup = export(client, alice).content
    bob_client, bob = second_user(outbox)
    for key in ("not-the-key", None):
        res = upload(bob_client, bob, backup, "b.json", master_key=key)
        assert res.status_code == 400 and res.json()["error"] == "invalid_master_key"
    assert entries(bob_client, bob) == []


def test_a_tampered_backup_row_fails_alone_and_a_bad_wrapper_fails_all(client, outbox):
    alice, _ = vault_user(client, outbox, "alice")
    new_entry(client, alice, site_name="One", password="pw-one-1")
    new_entry(client, alice, site_name="Two", password="pw-two-2")
    doc = export(client, alice).json()
    bob_client, bob = second_user(outbox)

    row = bytearray(__import__("base64").b64decode(doc["entries"][0]["fields"]))
    row[15] ^= 1
    doc["entries"][0]["fields"] = __import__("base64").b64encode(bytes(row)).decode()
    res = upload(bob_client, bob, json.dumps(doc), "b.json", master_key=MASTER_KEY).json()
    assert res["imported"] == 1 and res["failed_rows"] == [{"row": 1, "reason": "integrity"}]

    doc["wrapped_dek"] = doc["wrapped_dek"][:-4] + "AAAA"
    assert (
        upload(bob_client, bob, json.dumps(doc), "b.json", master_key=MASTER_KEY).status_code == 400
    )


def test_crafted_backup_cannot_demand_unbounded_argon2_memory(client, outbox):
    alice, _ = vault_user(client, outbox, "alice")
    doc = export(client, alice).json()
    doc["kdf"]["memory_kib"] = 64 * 1024 * 1024  # 64 GiB
    res = upload(client, alice, json.dumps(doc), "b.json", master_key=MASTER_KEY)
    assert res.status_code == 400 and res.json()["error"] == "invalid_import"


# --- activity log ---


def test_activity_lists_only_my_events_newest_first_without_secrets(client, outbox):
    alice, _ = vault_user(client, outbox, "alice")
    client.post("/api/vault/unlock", json={"master_key": "wrong-key-wrong"}, headers=alice)
    export(client, alice)
    bob_client, bob = second_user(outbox)
    body = client.get("/api/account/activity", headers=alice).json()
    types = [e["type"] for e in body["events"]]
    assert types[0] == "export" and "unlock_failed" in types and "login_ok" in types
    assert all(set(e) == {"type", "ip", "created_at"} for e in body["events"])
    assert all(e["created_at"].endswith("Z") for e in body["events"])
    assert (
        len(bob_client.get("/api/account/activity", headers=bob).json()["events"]) == 1
    )  # his own login_ok
    assert "wrong-key" not in str(body) and MASTER_KEY not in str(body)


def test_activity_limit_is_validated(client, outbox):
    alice, _ = vault_user(client, outbox, "alice")
    assert (
        client.get("/api/account/activity", params={"limit": 1}, headers=alice).status_code == 200
    )
    assert (
        len(
            client.get("/api/account/activity", params={"limit": 1}, headers=alice).json()["events"]
        )
        == 1
    )
    for bad in (0, 201, "x"):
        assert (
            client.get("/api/account/activity", params={"limit": bad}, headers=alice).status_code
            == 422
        )
