"""Application settings, read from environment variables (see .env.example).

Secrets and environment-specific values never live in source code.
The app refuses to start with missing, short or placeholder secrets (unless DEBUG=true).
"""

import logging
import os
import secrets


def _env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes"}


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/vaultguard.db")
DEBUG = _env_bool("DEBUG", default=False)  # secure default: off
COOKIE_SECURE = _env_bool("COOKIE_SECURE", default=False)  # true when served over HTTPS

ACCESS_TOKEN_MINUTES = _env_int("ACCESS_TOKEN_MINUTES", 10)
REFRESH_TOKEN_DAYS = _env_int("REFRESH_TOKEN_DAYS", 7)
VAULT_IDLE_MINUTES = _env_int("VAULT_IDLE_MINUTES", 10)

MAX_FAILED_ATTEMPTS = _env_int("MAX_FAILED_ATTEMPTS", 5)
LOCKOUT_MINUTES = _env_int("LOCKOUT_MINUTES", 15)

OTP_TTL_MINUTES = _env_int("OTP_TTL_MINUTES", 10)
OTP_MAX_ATTEMPTS = _env_int("OTP_MAX_ATTEMPTS", 5)
OTP_RESEND_SECONDS = _env_int("OTP_RESEND_SECONDS", 60)

# Argon2id for the master key (RFC 9106 low-memory option). Saved per user at vault setup.
ARGON2_TIME_COST = _env_int("ARGON2_TIME_COST", 3)
ARGON2_MEMORY_KIB = _env_int("ARGON2_MEMORY_KIB", 65536)
ARGON2_PARALLELISM = _env_int("ARGON2_PARALLELISM", 4)

HIBP_ENABLED = _env_bool("HIBP_ENABLED", default=True)
HIBP_TIMEOUT_SECONDS = _env_int("HIBP_TIMEOUT_SECONDS", 3)

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = _env_int("SMTP_PORT", 587)
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM")

MIN_SECRET_LENGTH = 32
PLACEHOLDER_PREFIX = "change-me"  # what .env.example ships with


def validate_secret(name: str, value: str | None, debug: bool) -> str:
    """Return a usable secret, or raise RuntimeError so the app never starts insecurely.

    In DEBUG a missing/weak secret is replaced with a random one for this run only.
    """
    weak = not value or len(value) < MIN_SECRET_LENGTH or value.startswith(PLACEHOLDER_PREFIX)
    if not weak:
        return value
    if debug:
        logging.getLogger("vaultguard").warning("%s is not set; using a temporary value", name)
        return secrets.token_urlsafe(48)
    raise RuntimeError(
        f"{name} must be set to at least {MIN_SECRET_LENGTH} random characters "
        '(python -c "import secrets; print(secrets.token_urlsafe(48))")'
    )


JWT_SECRET = validate_secret("JWT_SECRET", os.getenv("JWT_SECRET"), DEBUG)
OTP_PEPPER = validate_secret("OTP_PEPPER", os.getenv("OTP_PEPPER"), DEBUG)
