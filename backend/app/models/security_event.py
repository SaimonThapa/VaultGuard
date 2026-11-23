"""security_events table. Deliberately has no free-text column, so a secret can't leak into it."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow

EVENT_TYPES = (
    "login_ok",
    "login_failed",
    "login_locked",
    "unlock_ok",
    "unlock_failed",
    "unlock_locked",
    "tamper_detected",
    "password_changed",
    "master_key_changed",
    "master_key_recovered",
    "vault_reset",
    "import",
    "export",
    "refresh_reuse",
)


class SecurityEvent(Base):
    __tablename__ = "security_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(30))
    ip: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
