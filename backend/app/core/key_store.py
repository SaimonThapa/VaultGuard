"""In-memory store of unlocked vault keys, keyed by session id. Never written to disk.

Needs a single uvicorn worker (memory isn't shared across processes). Lock, logout, idle expiry
and a server restart all drop the key.
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.config import VAULT_IDLE_MINUTES
from app.db import utcnow


@dataclass
class UnlockedVault:
    user_id: int
    dek: bytes
    guesses_log10: float | None = None  # master-key strength for the health check (memory only)
    last_used: datetime = field(default_factory=utcnow)
    hibp_cache: dict[str, dict[str, int]] = field(default_factory=dict)


_lock = threading.Lock()
_store: dict[str, UnlockedVault] = {}


def _expired(vault: UnlockedVault, now: datetime) -> bool:
    return now - vault.last_used > timedelta(minutes=VAULT_IDLE_MINUTES)


def put(session_id: str, user_id: int, dek: bytes, guesses_log10: float | None = None) -> None:
    with _lock:
        _store[session_id] = UnlockedVault(user_id, dek, guesses_log10)


def get(session_id: str) -> UnlockedVault | None:
    """Return the unlocked vault and refresh its idle timer; None if locked or idle too long."""
    with _lock:
        vault = _store.get(session_id)
        if vault is None:
            return None
        now = utcnow()
        if _expired(vault, now):
            del _store[session_id]
            return None
        vault.last_used = now
        return vault


def is_unlocked(session_id: str) -> bool:
    """Like get() but doesn't refresh the idle timer (used by status polling)."""
    with _lock:
        vault = _store.get(session_id)
        if vault is None:
            return False
        if _expired(vault, utcnow()):
            del _store[session_id]
            return False
        return True


def drop(session_id: str) -> None:
    with _lock:
        _store.pop(session_id, None)


def drop_user(user_id: int, except_session: str | None = None) -> None:
    """Drop every session of a user (optionally keeping one)."""
    with _lock:
        for sid in [s for s, v in _store.items() if v.user_id == user_id and s != except_session]:
            del _store[sid]


def clear() -> None:
    with _lock:
        _store.clear()
