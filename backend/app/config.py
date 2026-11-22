"""Application settings, read from environment variables (see .env.example).

Secrets and environment-specific values never live in source code.
"""

import os


def _env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes"}


FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/vaultguard.db")
DEBUG = _env_bool("DEBUG", default=False)  # secure default: off
