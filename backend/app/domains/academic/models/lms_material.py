from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.types import Uuid
from sqlmodel import Field, SQLModel


class LmsMaterial(SQLModel, table=True):
    __tablename__ = "lms_materials"

    id: int | None = Field(default=None, primary_key=True)
    public_id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(Uuid(as_uuid=True, native_uuid=False), nullable=False, unique=True),
    )
    unit_id: int = Field(
        sa_column=Column(
            Integer, ForeignKey("lms_units.id", ondelete="CASCADE"), nullable=False
        )
    )
    title: str = Field(sa_column=Column(String(255), nullable=False))
    type: str = Field(sa_column=Column(String(20), nullable=False))
    content: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    file_key: str | None = Field(default=None, sa_column=Column(String(500), nullable=True))
    file_name: str | None = Field(default=None, sa_column=Column(String(255), nullable=True))
    order_index: int = Field(default=0, nullable=False)
    is_published: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        ),
    )
