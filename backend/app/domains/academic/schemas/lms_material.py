from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, model_validator
from sqlmodel import SQLModel


class MaterialCreate(SQLModel):
    title: str
    type: Literal['TEXT', 'PDF', 'LINK', 'VIDEO', 'FILE']
    content: str | None = None
    order_index: int = 0
    is_published: bool = False


class MaterialRead(SQLModel):
    model_config = ConfigDict(from_attributes=True)

    public_id: UUID
    title: str
    type: Literal['TEXT', 'PDF', 'LINK', 'VIDEO', 'FILE']
    content: str | None
    has_file: bool = False
    file_name: str | None = None
    order_index: int
    is_published: bool
    created_at: datetime
    updated_at: datetime

    @model_validator(mode='before')
    @classmethod
    def _compute_has_file(cls, data):
        if hasattr(data, 'file_key'):
            file_key = data.file_key
        elif isinstance(data, dict):
            file_key = data.get('file_key')
        else:
            file_key = None
        if isinstance(data, dict):
            data['has_file'] = bool(file_key)
        else:
            data = dict(
                public_id=data.public_id,
                title=data.title,
                type=data.type,
                content=data.content,
                has_file=bool(file_key),
                file_name=getattr(data, 'file_name', None),
                order_index=data.order_index,
                is_published=data.is_published,
                created_at=data.created_at,
                updated_at=data.updated_at,
            )
        return data


class MaterialUpdate(SQLModel):
    title: str | None = None
    type: Literal['TEXT', 'PDF', 'LINK', 'VIDEO', 'FILE'] | None = None
    content: str | None = None
    order_index: int | None = None
    is_published: bool | None = None
