"""users table (salts, hashes and wrapped keys only, never raw secrets) + auth request schemas."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    StringConstraints,
    ValidationInfo,
    field_validator,
)
from sqlalchemy import Boolean, DateTime, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core import passwords
from app.db import Base, utcnow


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)  # lowercase
    email: Mapped[str] = mapped_column(String(254), unique=True)  # lowercase
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    password_hash: Mapped[str] = mapped_column(String)  # Argon2id PHC string

    # Vault key material: all null until the vault is set up.
    kdf_time_cost: Mapped[int | None] = mapped_column(Integer)
    kdf_memory_kib: Mapped[int | None] = mapped_column(Integer)
    kdf_parallelism: Mapped[int | None] = mapped_column(Integer)
    master_salt: Mapped[bytes | None] = mapped_column(LargeBinary)
    master_verifier: Mapped[bytes | None] = mapped_column(LargeBinary)
    wrapped_dek_master: Mapped[bytes | None] = mapped_column(LargeBinary)  # nonce|ct|tag
    recovery_salt: Mapped[bytes | None] = mapped_column(LargeBinary)
    wrapped_dek_recovery: Mapped[bytes | None] = mapped_column(LargeBinary)

    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    login_locked_until: Mapped[datetime | None] = mapped_column(DateTime)
    failed_unlock_count: Mapped[int] = mapped_column(Integer, default=0)
    unlock_locked_until: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    @property
    def vault_set_up(self) -> bool:
        return self.wrapped_dek_master is not None


# --- Request schemas (product_backend.md §4). Unknown fields are rejected; whitespace is
# stripped everywhere except secrets. ---

Username = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_.-]+$"
    ),
]
OtpCode = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\d{6}$")]
NewPassword = Annotated[str, StringConstraints(min_length=12, max_length=128)]


def require_strong(secret: str, user_inputs: list[str]) -> str:
    score, _ = passwords.strength(secret, user_inputs)
    if score < 3:
        raise ValueError("too weak")
    return secret


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SignupIn(Strict):
    username: Username
    email: EmailStr
    password: NewPassword

    @field_validator("password")
    @classmethod
    def _strong(cls, value: str, info: ValidationInfo) -> str:
        data = info.data
        return require_strong(value, [data.get("username", ""), data.get("email", "")])


class VerifyEmailIn(Strict):
    username: Username
    code: OtpCode


class ResendIn(Strict):
    username: Annotated[str, StringConstraints(strip_whitespace=True, max_length=64)]


class LoginIn(Strict):
    # Deliberately loose: a malformed username is just a failed login (401), not a 422.
    username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class ForgotPasswordIn(Strict):
    email: EmailStr


class ResetPasswordIn(Strict):
    email: EmailStr
    code: OtpCode
    new_password: NewPassword

    @field_validator("new_password")
    @classmethod
    def _strong(cls, value: str, info: ValidationInfo) -> str:
        return require_strong(value, [info.data.get("email", "")])


StrongKey = Annotated[
    str,
    StringConstraints(min_length=12, max_length=256),
    AfterValidator(lambda value: require_strong(value, [])),
]


class MasterKeyIn(Strict):
    """Setting a master key: length and strength are enforced here, equality with the account
    password in the controller (that needs the stored hash)."""

    master_key: StrongKey


class UnlockIn(Strict):
    master_key: Annotated[str, StringConstraints(min_length=1, max_length=256)]


class OtpRequestIn(Strict):
    purpose: Literal["recover_master", "reset_vault"]


class RecoverIn(Strict):
    code: OtpCode
    recovery_key: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    new_master_key: StrongKey


class ChangeMasterKeyIn(Strict):
    new_master_key: StrongKey


class ResetVaultIn(Strict):
    code: OtpCode
    new_master_key: StrongKey


class ChangePasswordIn(Strict):
    current_password: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    new_password: NewPassword
