from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict
from sqlmodel import SQLModel


class SubmissionRead(SQLModel):
    model_config = ConfigDict(from_attributes=True)

    public_id: UUID
    content: str | None
    file_name: str | None
    status: Literal['PENDING', 'SUBMITTED', 'GRADED']
    score: int | None
    feedback: str | None
    submitted_at: datetime | None
    graded_at: datetime | None
    created_at: datetime
    updated_at: datetime
    # Marcador suave de entrega tardía. No vive en el modelo: lo calcula la ruta
    # comparando submitted_at contra el due_date de la actividad (que no está en
    # el ORM de la submission). Default False para el caso sin fecha límite.
    is_late: bool = False


class SubmissionUpdate(SQLModel):
    content: str | None = None
    file_name: str | None = None
    status: Literal['PENDING', 'SUBMITTED', 'GRADED'] | None = None
    score: int | None = None
    feedback: str | None = None
    graded_by: int | None = None
    graded_at: datetime | None = None
    submitted_at: datetime | None = None
