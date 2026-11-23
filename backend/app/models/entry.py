"""entries table + request schemas. Site name and URL are plaintext (searchable); the username,
password and notes are encrypted."""

from datetime import datetime
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import StringConstraints, field_validator
from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow
from app.models.user import Strict


class Entry(Base):
    __tablename__ = "entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID4, made by the app
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    site_name: Mapped[str] = mapped_column(String(100))
    site_url: Mapped[str | None] = mapped_column(String(2048))
    # AES-256-GCM blobs (nonce|ct|tag); AAD is "{user_id}|{entry_id}|{field}".
    username_enc: Mapped[bytes] = mapped_column(LargeBinary)
    password_enc: Mapped[bytes] = mapped_column(LargeBinary)
    notes_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    rotation_days: Mapped[int | None] = mapped_column(Integer)
    password_changed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


def normalize_url(value: str | None) -> str | None:
    """Empty -> None. A missing scheme becomes https. Only http(s) URLs with a host are allowed."""
    value = (value or "").strip()
    if not value:
        return None
    if "://" not in value:
        value = f"https://{value}"
    parts = urlsplit(value)
    try:
        port_ok = parts.port is None or parts.port > 0  # raises on "javascript:alert(1)"-style junk
    except ValueError:
        port_ok = False
    bad = (
        parts.scheme not in ("http", "https")
        or not parts.hostname
        or not port_ok
        or any(c.isspace() for c in value)
    )
    if bad:
        raise ValueError("bad url")
    return value


class EntryIn(Strict):
    site_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ]
    site_url: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=2048)] = (
        None
    )
    username: Annotated[str, StringConstraints(max_length=256)] = ""
    password: Annotated[str, StringConstraints(min_length=1, max_length=256)]
    notes: Annotated[str | None, StringConstraints(max_length=2000)] = None
    rotation_days: int | None = None

    @field_validator("site_url")
    @classmethod
    def _url(cls, value: str | None) -> str | None:
        return normalize_url(value)

    @field_validator("rotation_days")
    @classmethod
    def _rotation(cls, value: int | None) -> int | None:
        if value is not None and not 1 <= value <= 3650:
            raise ValueError("out of range")
        return value
