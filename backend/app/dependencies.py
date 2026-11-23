"""FastAPI dependencies that guard routes. Every non-public route depends on one of these."""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import key_store, tokens
from app.db import get_db, utcnow
from app.errors import AppError
from app.models import RefreshToken, User

_bearer = HTTPBearer(auto_error=False)
UNAUTHORIZED = AppError(401, "unauthorized", "Please log in again.")


class CurrentSession:
    """Who is calling: the user plus the session id that ties together tokens and the vault key."""

    def __init__(self, user: User, session_id: str):
        self.user = user
        self.session_id = session_id


def get_session(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> CurrentSession:
    if credentials is None:
        raise UNAUTHORIZED
    decoded = tokens.decode_access_token(credentials.credentials)
    if decoded is None:
        raise UNAUTHORIZED
    user_id, session_id = decoded
    user = db.get(User, user_id)
    if user is None or not user.email_verified:
        raise UNAUTHORIZED
    # Logout revokes the session's refresh tokens, which also kills its access tokens at once.
    live = db.scalar(
        select(RefreshToken.id)
        .where(
            RefreshToken.session_id == session_id,
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > utcnow(),
        )
        .limit(1)
    )
    if live is None:
        raise UNAUTHORIZED
    return CurrentSession(user, session_id)


def get_current_user(session: Annotated[CurrentSession, Depends(get_session)]) -> User:
    return session.user


class Unlocked(CurrentSession):
    """A session whose vault is unlocked: also carries the in-memory vault (the DEK)."""

    def __init__(self, session: CurrentSession, vault: key_store.UnlockedVault):
        super().__init__(session.user, session.session_id)
        self.vault = vault

    @property
    def dek(self) -> bytes:
        return self.vault.dek


def get_unlocked(session: Annotated[CurrentSession, Depends(get_session)]) -> Unlocked:
    """Auth plus an unlocked vault, else 423. Touching the key store refreshes the idle timer."""
    vault = key_store.get(session.session_id)
    if vault is None or vault.user_id != session.user.id:
        raise AppError(423, "vault_locked", "Unlock your vault first.")
    return Unlocked(session, vault)
