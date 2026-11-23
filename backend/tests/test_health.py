from datetime import timedelta

import pytest

from app import config
from app.controllers import health
from app.db import SessionLocal, utcnow
from app.models import Entry
from app.services import hibp

from .conftest import new_entry, vault_user

STRONG_A = "Gh-Secret!2026-xyz-Alpha"
STRONG_B = "Nf-Secret!2026-abc-Bravo"


def report(client, headers):
    res = client.get("/api/vault/health", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


# --- score math (pure) ---


def test_score_is_the_weighted_average_of_available_metrics():
    metrics = {
        "integrity": 100,
        "master_key": 100,
        "weak": 50,
        "reused": 100,
        "breached": 100,
        "rotation": 100,
    }
    # 100 - weight(weak)=20 x 50/100 lost = 90
    assert health.compute_score(metrics, integrity_failed=False) == 90


def test_unavailable_checks_drop_out_and_weights_renormalize():
    metrics = {
        "integrity": 100,
        "master_key": 100,
        "weak": 0,
        "reused": 100,
        "breached": None,
        "rotation": 100,
    }
    # available weights = 85; weak (20) is the only loss: 100 x (65/85) = 76.47
    assert health.compute_score(metrics, integrity_failed=False) == 76


def test_an_integrity_failure_caps_the_score_at_40():
    metrics = {
        "integrity": 90,
        "master_key": 100,
        "weak": 100,
        "reused": 100,
        "breached": 100,
        "rotation": 100,
    }
    assert health.compute_score(metrics, integrity_failed=False) > 90
    assert health.compute_score(metrics, integrity_failed=True) == 40


@pytest.mark.parametrize(
    ("metric", "band"),
    [
        (0, "critical"),
        (39, "critical"),
        (40, "poor"),
        (59, "poor"),
        (60, "fair"),
        (74, "fair"),
        (75, "good"),
        (89, "good"),
        (90, "excellent"),
        (100, "excellent"),
        (None, "unavailable"),
    ],
)
def test_band_boundaries_match_the_ui_scale(metric, band):
    assert health.band_for(metric) == band


def test_crack_time_wording():
    assert health.crack_time_text(3) == "under a second"
    assert health.crack_time_text(21) == "~2 billion years"
    assert health.crack_time_text(32) == "~10^20 years"


# --- the endpoint ---


def test_empty_vault_scores_entry_checks_at_100(client, outbox):
    headers, _ = vault_user(client, outbox)
    body = report(client, headers)
    checks = body["checks"]
    for name in ("integrity", "weak", "reused", "rotation"):
        assert checks[name]["metric"] == 100
    assert checks["breached"]["band"] == "unavailable"  # HIBP is off in tests
    assert checks["master_key"]["metric"] > 0 and "crack_time_argon2" in checks["master_key"]
    assert body["band"] == health.band_for(body["score"])


def test_report_needs_an_unlocked_vault(client, outbox):
    headers, _ = vault_user(client, outbox)
    client.post("/api/vault/lock", headers=headers)
    assert client.get("/api/vault/health", headers=headers).status_code == 423


def test_weak_reused_and_rotation_findings(client, outbox):
    headers, _ = vault_user(client, outbox)
    new_entry(client, headers, site_name="Strong", password=STRONG_A)
    new_entry(client, headers, site_name="Weak", password="password1")
    new_entry(client, headers, site_name="Twin 1", password=STRONG_B)
    new_entry(client, headers, site_name="Twin 2", password=STRONG_B)
    late = new_entry(
        client, headers, site_name="Late", password="Zr-Unique-Pw-9981-qq", rotation_days=30
    ).json()
    with SessionLocal() as db:
        db.get(Entry, late["id"]).password_changed_at = utcnow() - timedelta(days=42)
        db.commit()

    checks = report(client, headers)["checks"]
    assert [e["site_name"] for e in checks["weak"]["entries"]] == ["Weak"]
    assert checks["weak"]["entries"][0]["zxcvbn_score"] < 3
    assert checks["weak"]["metric"] == 80  # 4 of 5 pass
    names = sorted(e["site_name"] for e in checks["reused"]["groups"][0])
    assert names == ["Twin 1", "Twin 2"] and len(checks["reused"]["groups"]) == 1
    assert checks["reused"]["metric"] == 60  # 3 of 5 are not in a reuse group
    assert checks["rotation"]["due"][0]["site_name"] == "Late"
    assert checks["rotation"]["due"][0]["days_overdue"] == 12
    assert checks["rotation"]["metric"] == 0  # the one tracked entry is overdue
    assert checks["rotation"]["tracked"] == 1
    assert report(client, headers)["entry_count"] == 5


def test_report_never_contains_a_password(client, outbox):
    headers, _ = vault_user(client, outbox)
    new_entry(client, headers, password="password1")
    new_entry(client, headers, site_name="Twin", password="password1")
    res = client.get("/api/vault/health", headers=headers)
    assert "password1" not in res.text
    assert "alice-dev" not in res.text  # usernames neither


def test_rotation_not_tracked_is_100(client, outbox):
    headers, _ = vault_user(client, outbox)
    new_entry(client, headers, password=STRONG_A)
    assert report(client, headers)["checks"]["rotation"]["metric"] == 100


# --- HIBP (network is always mocked) ---


@pytest.fixture
def hibp_on(monkeypatch):
    monkeypatch.setattr(config, "HIBP_ENABLED", True)
    calls = []

    def fake_fetch(prefix):
        calls.append(prefix)
        import hashlib

        pwned = hashlib.sha1(b"password1", usedforsecurity=False).hexdigest().upper()  # noqa: S324
        body = "0018A45C4D1DEF81644B54AB7F969B88D65:0\r\n"  # padding row, count 0
        if prefix == pwned[:5]:
            body += f"{pwned[5:]}:3730471\r\n"
        return body

    monkeypatch.setattr(hibp, "fetch_range", fake_fetch)
    return calls


def test_breached_passwords_are_flagged_and_only_the_prefix_is_sent(client, outbox, hibp_on):
    headers, _ = vault_user(client, outbox)
    new_entry(client, headers, site_name="Pwned", password="password1")
    new_entry(client, headers, site_name="Fine", password=STRONG_A)
    breached = report(client, headers)["checks"]["breached"]
    assert [e["site_name"] for e in breached["entries"]] == ["Pwned"]
    assert breached["entries"][0]["count"] == 3730471
    assert breached["metric"] == 50
    assert all(
        len(prefix) == 5 for prefix in hibp_on
    )  # k-anonymity: 5 characters, never the password


def test_hibp_results_are_cached_for_the_session(client, outbox, hibp_on):
    headers, _ = vault_user(client, outbox)
    new_entry(client, headers, password=STRONG_A)
    report(client, headers)
    first = len(hibp_on)
    report(client, headers)
    assert len(hibp_on) == first


def test_hibp_outage_makes_the_check_unavailable_not_an_error(client, outbox, hibp_on, monkeypatch):
    def boom(prefix):
        raise TimeoutError

    monkeypatch.setattr(hibp, "fetch_range", boom)
    headers, _ = vault_user(client, outbox)
    new_entry(client, headers, password=STRONG_A)
    body = report(client, headers)
    assert body["checks"]["breached"]["metric"] is None
    assert body["checks"]["breached"]["band"] == "unavailable"
    assert body["score"] > 0  # the rest still scores
