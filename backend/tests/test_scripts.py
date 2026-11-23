"""The demo scripts run for real (in a throwaway database) and produce what the demo needs."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent


@pytest.fixture
def demo_db(tmp_path):
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{tmp_path}/demo.db",
        "ARGON2_TIME_COST": "1",
        "ARGON2_MEMORY_KIB": "64",
        "ARGON2_PARALLELISM": "1",
    }

    def run(*args):
        return subprocess.run(  # noqa: S603
            [sys.executable, "-m", *args],
            cwd=BACKEND,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )

    return tmp_path / "demo.db", run


def test_reset_db_seeds_alice_and_bob_with_findings(demo_db):
    path, run = demo_db
    result = run("scripts.reset_db")
    assert result.returncode == 0, result.stderr
    assert "recovery key" in result.stdout and "alice" in result.stdout
    db = sqlite3.connect(path)
    assert db.execute("SELECT COUNT(*) FROM users WHERE email_verified = 1").fetchone()[0] == 2
    counts = dict(
        db.execute(
            "SELECT u.username, COUNT(e.id) FROM users u JOIN entries e ON e.user_id = u.id GROUP BY u.username"
        )
    )
    assert counts == {"alice": 12, "bob": 3}
    assert (
        db.execute(
            "SELECT COUNT(*) FROM entries WHERE rotation_days IS NOT NULL AND password_changed_at < datetime('now', '-60 days')"
        ).fetchone()[0]
        >= 1
    )


def test_show_db_prints_ciphertext_not_secrets(demo_db):
    path, run = demo_db
    run("scripts.reset_db")
    out = run("scripts.show_db").stdout
    assert "ENTRIES" in out and "GitHub" in out
    for secret in ("Gh-Secret", "Alice-Demo-Passphrase", "7K3Q-9XWM", "password123"):
        assert secret not in out


def test_tamper_entry_flips_exactly_one_bit(demo_db):
    path, run = demo_db
    run("scripts.reset_db")
    db = sqlite3.connect(path)
    entry_id, before = db.execute("SELECT id, password_enc FROM entries LIMIT 1").fetchone()
    result = run("scripts.tamper_entry", entry_id)
    assert result.returncode == 0, result.stderr
    after = (
        sqlite3.connect(path)
        .execute("SELECT password_enc FROM entries WHERE id = ?", (entry_id,))
        .fetchone()[0]
    )
    assert (
        len(after) == len(before) and sum(a != b for a, b in zip(before, after, strict=True)) == 1
    )
    assert run("scripts.tamper_entry", "no-such-id").returncode == 1
