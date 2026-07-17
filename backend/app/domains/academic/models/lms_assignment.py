from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.types import Uuid
from sqlmodel import Field, SQLModel

# Los tres logros/ejes de robótica bajo los que se agrupa cada actividad.
# Claves ASCII para el ENUM de MySQL; las etiquetas visibles ("Diseñar", …)
# viven en el frontend.
LOGRO_VALUES = ("disenar", "programar", "robotizar")


class LmsAssignment(SQLModel, table=True):
    __tablename__ = "lms_assignments"

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
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    due_date: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    max_score: int = Field(default=100, nullable=False)
    logro: str | None = Field(
        default=None,
        sa_column=Column(Enum(*LOGRO_VALUES, name="logro"), nullable=True),
    )
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
