"""Demo 1 helper: flip ONE byte of an entry's stored password ciphertext, directly in SQLite.

    python -m scripts.tamper_entry <entry_id>

This is what an attacker with write access to the database file could do. Afterwards, unlock the
vault and open the dashboard: the entry is flagged "Tampered" and the score drops to 40 or less.
List entry ids with:  python -m scripts.show_db"""

from scripts import _env  # noqa: F401  (must come first: loads backend/.env)

import sqlite3
import sys
from pathlib import Path

from app.config import DATABASE_URL


def main(entry_id: str) -> int:
    path = Path(DATABASE_URL.removeprefix("sqlite:///"))
    if not path.exists():
        print(f"No database at {path}. Run: python -m scripts.reset_db")
        return 1
    with sqlite3.connect(path) as db:
        row = db.execute("SELECT password_enc FROM entries WHERE id = ?", (entry_id,)).fetchone()
        if row is None:
            print("No entry with that id (see: python -m scripts.show_db).")
            return 1
        blob = bytearray(row[0])
        blob[14] ^= 0x01  # inside the ciphertext, after the 12-byte nonce
        db.execute("UPDATE entries SET password_enc = ? WHERE id = ?", (bytes(blob), entry_id))
    print(f"Flipped one bit of byte 14 of password_enc for entry {entry_id}.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python -m scripts.tamper_entry <entry_id>")
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
