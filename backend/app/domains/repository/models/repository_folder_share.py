from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel

from app.domains.academic.models.school import WorkLine


class ShareScopeType(str, Enum):
    work_line = "work_line"
    school = "school"


class RepositoryFolderShare(SQLModel, table=True):
    """Compartición de una carpeta del repositorio con una línea o un colegio.

    Una carpeta puede tener varias filas (compartida con varias líneas y/o
    colegios). Los archivos no tienen shares propios: heredan de su carpeta.
    El scope efectivo se resuelve subiendo por `parent_id` hasta el ancestro
    más cercano con shares (override en cualquier subcarpeta). Ver feature
    "Repositorio LMS - Compartir Carpetas por Linea y Colegio".
    """

    __tablename__ = "repository_folder_shares"
    __table_args__ = (
        UniqueConstraint(
            "folder_id",
            "scope_type",
            "work_line",
            "school_id",
            name="uq_repository_folder_shares_scope",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    folder_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("repository_folders.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    scope_type: ShareScopeType = Field(
        sa_column=Column(
            SAEnum(ShareScopeType, values_callable=lambda x: [e.value for e in x]),
            nullable=False,
        )
    )
    # Solo uno de los dos según scope_type.
    work_line: WorkLine | None = Field(
        default=None,
        sa_column=Column(
            SAEnum(WorkLine, values_callable=lambda x: [e.value for e in x]),
            nullable=True,
        ),
    )
    school_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("schools.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    created_by: int | None = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("users.id"), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime, nullable=False),
    )
