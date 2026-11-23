"""Wipe the database and seed fictional demo users (run from backend/ with the venv active):

    python -m scripts.reset_db

Stop the API first (it holds the SQLite file open). Everything created here is fictional and is
printed below, so it can also be listed in the README's test-accounts section."""

from scripts import _env  # noqa: F401  (must come first: loads backend/.env)

import sys
import uuid
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

from app.config import DATABASE_URL
from app.controllers import entries as entry_logic
from app.controllers import vault as vault_logic
from app.core import passwords
from app.db import Base, SessionLocal, engine, utcnow
from app.models import Entry, User
from app.models.entry import EntryIn

ACCOUNTS = {
    "alice": {
        "email": "alice@demo.mail",
        "password": "Alice-Demo-Passphrase-2026!",
        "master_key": "7K3Q-9XWM-2PDA-H8RT-Y4NC-6VBE-1Z",
        "entries": [
            (
                "GitHub",
                "github.com",
                "alice-dev",
                "Gh-Secret!2026-xyz-Alpha",
                "Personal account",
                None,
                0,
            ),
            (
                "GitHub",
                "github.com",
                "alice-work",
                "Wk-Secret!2026-qrs-Bravo",
                "Work, SSO enabled",
                90,
                34,
            ),
            (
                "Gmail",
                "mail.google.com",
                "alice@demo.mail",
                "Gm-Secret!2026-lmn-Charlie",
                None,
                None,
                0,
            ),
            ("Amazon", "amazon.com", "alice@demo.mail", "Am-Secret!2026-tuv-Delta", None, None, 0),
            (
                "Bank of Demo",
                "bank.example.com",
                "alice.demo",
                "Bk-Secret!2026-hij-Echo",
                "Checking",
                180,
                20,
            ),
            ("Spotify", "spotify.com", "alice", "Sp-Secret!2026-def-Foxtrot", None, None, 0),
            ("Dropbox", "dropbox.com", "alice@demo.mail", "Db-Secret!2026-abc-Golf", None, None, 0),
            # findings for the health dashboard:
            (
                "Netflix",
                "netflix.com",
                "alice@demo.mail",
                "password123",
                None,
                None,
                0,
            ),  # weak + breached
            ("Old Forum", "forum.example.org", "alice", "qwerty12", None, None, 0),  # weak
            (
                "Photo Site",
                "photos.example.com",
                "alice",
                "Shared-Pw-2026-Zeta-91",
                None,
                None,
                0,
            ),  # reused
            (
                "Print Shop",
                "prints.example.com",
                "alice",
                "Shared-Pw-2026-Zeta-91",
                None,
                None,
                0,
            ),  # reused
            (
                "Cloud Backup",
                "backup.example.com",
                "alice",
                "Cb-Secret!2026-ghi-Hotel",
                None,
                30,
                75,
            ),  # overdue
        ],
    },
    "bob": {  # the IDOR victim: alice must never be able to read these
        "email": "bob@demo.mail",
        "password": "Bob-Demo-Passphrase-2026!",
        "master_key": "Bobs-Demo-Master-Key-2026-Orbit!",
        "entries": [
            ("Bob's Bank", "bank.example.com", "bob", "Bb-Secret!2026-uvw-India", None, None, 0),
            (
                "Bob's Mail",
                "mail.example.net",
                "bob@demo.mail",
                "Bm-Secret!2026-xyz-Juliet",
                None,
                None,
                0,
            ),
            (
                "Bob's Notes",
                "notes.example.net",
                "bob",
                "Bn-Secret!2026-abc-Kilo",
                "Private",
                None,
                0,
            ),
        ],
    },
}


def wipe_database() -> None:
    engine.dispose()
    if DATABASE_URL.startswith("sqlite:///"):
        Path(DATABASE_URL.removeprefix("sqlite:///")).unlink(missing_ok=True)
    Base.metadata.create_all(engine)


def seed_account(db, username: str, spec: dict) -> str:
    user = User(
        username=username,
        email=spec["email"],
        email_verified=True,
        password_hash=passwords.hash_password(spec["password"]),
    )
    db.add(user)
    db.flush()
    dek, recovery_key = vault_logic.install_keys(user, spec["master_key"])
    unlocked = SimpleNamespace(user=user, dek=dek)  # the two things encrypt_into needs
    for site, url, name, password, notes, rotation, age_days in spec["entries"]:
        entry = Entry(id=str(uuid.uuid4()), user_id=user.id)
        data = EntryIn(
            site_name=site,
            site_url=url,
            username=name,
            password=password,
            notes=notes,
            rotation_days=rotation,
        )
        entry_logic.encrypt_into(entry, unlocked, data)
        entry.password_changed_at = utcnow() - timedelta(days=age_days)
        db.add(entry)
    db.commit()
    return recovery_key


def main() -> None:
    wipe_database()
    with SessionLocal() as db:
        for username, spec in ACCOUNTS.items():
            recovery_key = seed_account(db, username, spec)
            print(f"\n{username}  ({spec['email']})  {len(spec['entries'])} entries")
            print(f"  account password : {spec['password']}")
            print(f"  master key       : {spec['master_key']}")
            print(f"  recovery key     : {recovery_key}")
    print("\nDone. Start the API and log in with the accounts above (all data is fictional).")


if __name__ == "__main__":
    sys.exit(main())
