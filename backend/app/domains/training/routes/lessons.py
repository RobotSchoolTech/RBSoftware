from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlmodel import Session

from app.core.database import get_session
from app.core.permissions import require_roles
from app.core.storage import storage_service
from app.domains.auth.dependencies import get_current_user
from app.domains.auth.models import User
from app.domains.training.repositories.lesson_repository import LessonRepository
from app.domains.training.repositories.module_repository import ModuleRepository
from app.domains.training.schemas.training_lesson import (
    LessonCreate,
    LessonRead,
    LessonUpdate,
)
from app.domains.training.services import TrainingService

router = APIRouter(prefix="/training", tags=["training – lessons"])
_svc = TrainingService()


@router.get("/modules/{module_id}/lessons", response_model=list[LessonRead])
def list_lessons(
    module_id: UUID,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    module = ModuleRepository(session).get_by_public_id(module_id)
    if module is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Módulo no encontrado")
    return [
        LessonRead.model_validate(l)
        for l in LessonRepository(session).list_by_module(module.id)
    ]


@router.post(
    "/modules/{module_id}/lessons",
    response_model=LessonRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_lesson(
    module_id: UUID,
    title: str = Form(...),
    type: str = Form(...),
    content: str | None = Form(default=None),
    duration_minutes: int | None = Form(default=None),
    order_index: int = Form(default=0),
    file: UploadFile | None = File(default=None),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN", "TRAINER", "SUPER_TRAINER")),
):
    file_bytes = None
    file_name = None
    if file is not None:
        file_bytes = await file.read()
        if len(file_bytes) > 100 * 1024 * 1024:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "El archivo excede 100 MB"
            )
        # El nombre —no el content-type que declara el cliente— es lo que decide
        # la extensión y el content-type con el que se guarda y se sirve.
        file_name = file.filename
    data = LessonCreate(
        title=title,
        type=type,
        content=content,
        duration_minutes=duration_minutes,
        order_index=order_index,
    )
    try:
        lesson = _svc.create_lesson(
            session, module_id, data, file_bytes, file_name, current_user.id
        )
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return LessonRead.model_validate(lesson)


class LessonFromRepositoryBody(BaseModel):
    title: str
    type: str
    file_id: str
    duration_minutes: int | None = None


@router.post(
    "/modules/{module_id}/lessons/from-repository",
    response_model=LessonRead,
    status_code=status.HTTP_201_CREATED,
)
def create_lesson_from_repository(
    module_id: UUID,
    body: LessonFromRepositoryBody,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN", "TRAINER", "SUPER_TRAINER")),
):
    data = LessonCreate(
        title=body.title,
        type=body.type,
        duration_minutes=body.duration_minutes,
    )
    try:
        lesson = _svc.create_lesson_from_repository(
            session, module_id, data, body.file_id, current_user.id
        )
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return LessonRead.model_validate(lesson)


@router.patch("/lessons/{lesson_id}", response_model=LessonRead)
def update_lesson(
    lesson_id: UUID,
    data: LessonUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("ADMIN", "TRAINER", "SUPER_TRAINER")),
):
    lesson = LessonRepository(session).get_by_public_id(lesson_id)
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lección no encontrada")
    updated = LessonRepository(session).update(lesson, data)
    return LessonRead.model_validate(updated)


class ReorderBody(BaseModel):
    lesson_ids: list[UUID]


@router.put(
    "/modules/{module_id}/lessons/reorder",
    response_model=list[LessonRead],
)
def reorder_lessons(
    module_id: UUID,
    body: ReorderBody,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("ADMIN", "TRAINER", "SUPER_TRAINER")),
):
    module = ModuleRepository(session).get_by_public_id(module_id)
    if module is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Módulo no encontrado")
    repo = LessonRepository(session)
    lessons = []
    for i, lesson_id in enumerate(body.lesson_ids):
        lesson = repo.get_by_public_id(lesson_id)
        if lesson is None or lesson.module_id != module.id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Lección {lesson_id} no pertenece al módulo",
            )
        lesson.order_index = i
        session.add(lesson)
        lessons.append(lesson)
    session.commit()
    for l in lessons:
        session.refresh(l)
    return [LessonRead.model_validate(l) for l in lessons]


class PublishBody(BaseModel):
    publish: bool


@router.post("/lessons/{lesson_id}/publish", response_model=LessonRead)
def publish_lesson(
    lesson_id: UUID,
    body: PublishBody,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("ADMIN", "TRAINER", "SUPER_TRAINER")),
):
    lesson = LessonRepository(session).get_by_public_id(lesson_id)
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lección no encontrada")
    updated = LessonRepository(session).update(
        lesson, LessonUpdate(is_published=body.publish)
    )
    return LessonRead.model_validate(updated)


@router.post("/lessons/{lesson_id}/complete", status_code=status.HTTP_204_NO_CONTENT)
def complete_lesson(
    lesson_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("TEACHER")),
):
    try:
        _svc.mark_lesson_completed(session, lesson_id, current_user.id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))


@router.get("/lessons/{lesson_id}/view")
def view_lesson(
    lesson_id: UUID,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    lesson = LessonRepository(session).get_by_public_id(lesson_id)
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lección no encontrada")
    if not lesson.file_key:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Esta lección no tiene archivo")
    # Servido seguro: la extensión del key decide inline vs. attachment y ancla
    # el content-type. Una lección creada desde el repositorio puede apuntar a
    # un archivo arbitrario (.html, .svg) → se descarga en vez de ejecutarse.
    url = storage_service.generate_view_url(lesson.file_key)
    return {"url": url}
