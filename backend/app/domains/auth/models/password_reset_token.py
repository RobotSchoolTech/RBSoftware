from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.types import Uuid
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.domains.auth.models.user import User


class PasswordResetToken(SQLModel, table=True):
    __tablename__ = "password_reset_tokens"

    id: int | None = Field(default=None, primary_key=True)
    public_id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(Uuid(as_uuid=True, native_uuid=False), nullable=False, unique=True),
    )
    user_id: int = Field(
        sa_column=Column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    )
    token_hash: str = Field(
        sa_column=Column(String(255), nullable=False, unique=True, index=True)
    )
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    used: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )

    user: "User" = Relationship(back_populates="password_reset_tokens")
