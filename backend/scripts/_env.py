"""Loads backend/.env into the environment so the scripts see the same settings as uvicorn.

Import this FIRST in every script (before anything from `app`), because app.config reads the
environment when it is imported. Values already set in the real environment win."""

import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def load() -> None:
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


load()
