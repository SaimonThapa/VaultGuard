"""Show what is actually stored on disk (the "stolen database" talking point):

    python -m scripts.show_db

Passwords are Argon2id hashes, keys are wrapped, and every secret field is ciphertext. Only site
names and URLs are readable (by design, so search works while locked)."""

from scripts import _env  # noqa: F401  (must come first: loads backend/.env)

import sqlite3
import sys
from pathlib import Path

from app.config import DATABASE_URL


def short(value, size=18) -> str:
    if isinstance(value, bytes):
        return f"{value.hex()[:size]}... ({len(value)} B)"
    text = str(value)
    return text if len(text) <= size else text[:size] + "..."


def main() -> int:
    path = Path(DATABASE_URL.removeprefix("sqlite:///"))
    if not path.exists():
        print(f"No database at {path}. Run: python -m scripts.reset_db")
        return 1
    db = sqlite3.connect(path)
    print(f"Database file: {path}\n")

    print("USERS (no plaintext secrets anywhere)")
    cols = "id, username, email, password_hash, master_salt, master_verifier, wrapped_dek_master, wrapped_dek_recovery"
    for row in db.execute(f"SELECT {cols} FROM users"):  # noqa: S608  (constant column list)
        print("  " + " | ".join(short(v) for v in row))

    print("\nENTRIES (site is plaintext; username, password, notes are AES-256-GCM ciphertext)")
    cols = "id, user_id, site_name, site_url, username_enc, password_enc, notes_enc"
    for row in db.execute(f"SELECT {cols} FROM entries ORDER BY user_id, site_name"):  # noqa: S608
        print("  " + " | ".join(short(v, 36 if i == 0 else 18) for i, v in enumerate(row)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
