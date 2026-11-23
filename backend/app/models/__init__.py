"""Import every model so Base.metadata knows all tables before create_all."""

from app.models.entry import Entry
from app.models.otp import Otp
from app.models.refresh_token import RefreshToken
from app.models.security_event import SecurityEvent
from app.models.user import User

__all__ = ["Entry", "Otp", "RefreshToken", "SecurityEvent", "User"]
