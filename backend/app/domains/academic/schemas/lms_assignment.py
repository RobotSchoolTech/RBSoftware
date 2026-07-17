from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict
from sqlmodel import SQLModel

Logro = Literal["disenar", "programar", "robotizar"]


class AssignmentCreate(SQLModel):
    title: str
    description: str | None = None
    due_date: datetime | None = None
    max_score: int = 100
    logro: Logro | None = None


class AssignmentRead(SQLModel):
    model_config = ConfigDict(from_attributes=True)

    public_id: UUID
    title: str
    description: str | None
    due_date: datetime | None
    max_score: int
    logro: str | None
    is_published: bool
    created_at: datetime
    updated_at: datetime


class AssignmentUpdate(SQLModel):
    title: str | None = None
    description: str | None = None
    due_date: datetime | None = None
    max_score: int | None = None
    logro: Logro | None = None
    is_published: bool | None = None
