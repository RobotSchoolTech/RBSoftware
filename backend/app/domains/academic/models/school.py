from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Enum as SAEnum, String, Text, func
from sqlalchemy.types import Uuid
from sqlmodel import Field, SQLModel


class WorkLine(str, Enum):
    kuntur = "kuntur"
    kuntur_abierto = "kuntur_abierto"
    ecua = "ecua"
    ecua_2 = "ecua_2"
    ecua_3 = "ecua_3"
    ares = "ares"
    robotschool = "robotschool"


class School(SQLModel, table=True):
    __tablename__ = "schools"

    id: int | None = Field(default=None, primary_key=True)
    public_id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(Uuid(as_uuid=True, native_uuid=False), nullable=False, unique=True),
    )
    name: str = Field(sa_column=Column(String(255), nullable=False))
    city: str | None = Field(default=None, sa_column=Column(String(100), nullable=True))
    address: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    contact_name: str | None = Field(
        default=None, sa_column=Column(String(100), nullable=True)
    )
    contact_email: str | None = Field(
        default=None, sa_column=Column(String(255), nullable=True)
    )
    contact_phone: str | None = Field(
        default=None, sa_column=Column(String(30), nullable=True)
    )
    work_line: WorkLine | None = Field(
        default=None,
        sa_column=Column(SAEnum(WorkLine, values_callable=lambda x: [e.value for e in x]), nullable=True),
    )
    is_active: bool = Field(default=True, nullable=False)
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
