from __future__ import annotations

from uuid import UUID

from typing import Any

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlmodel import Session

from app.core.database import get_session
from app.core.storage import storage_service
from app.domains.academic.repositories import MaterialRepository, UnitRepository
from app.domains.academic.schemas import MaterialCreate, MaterialRead
from app.domains.academic.services import AcademicService
from app.core.permissions import require_roles
from app.domains.auth.dependencies import get_current_user
from app.domains.auth.models import User

router = APIRouter(prefix="/academic", tags=["academic – materials"])
_svc = AcademicService()


@router.get("/units/{unit_id}/materials", response_model=list[MaterialRead])
def list_materials(
    unit_id: UUID,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    unit = UnitRepository(session).get_by_public_id(unit_id)
    if unit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unit not found")
    return [
        MaterialRead.model_validate(m)
        for m in MaterialRepository(session).list_by_unit(unit.id)
    ]


@router.post(
    "/units/{unit_id}/materials",
    response_model=MaterialRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_material(
    unit_id: UUID,
    title: str = Form(...),
    type: str = Form(...),
    content: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN", "TEACHER")),
):
    unit = UnitRepository(session).get_by_public_id(unit_id)
    if unit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unit not found")
    file_bytes = None
    content_type = None
    if file is not None:
        file_bytes = await file.read()
        if len(file_bytes) > 100 * 1024 * 1024:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "File size exceeds 100 MB limit")
        content_type = file.content_type
    data = MaterialCreate(title=title, type=type, content=content)
    try:
        material = _svc.add_material(
            session, unit.id, data, file_bytes, content_type, current_user.id
        )
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return MaterialRead.model_validate(material)


class MaterialFromRepositoryBody(BaseModel):
    title: str
    file_id: str


@router.post(
    "/units/{unit_id}/materials/from-repository",
    response_model=MaterialRead,
    status_code=status.HTTP_201_CREATED,
)
def add_material_from_repository(
    unit_id: UUID,
    body: MaterialFromRepositoryBody,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN", "TEACHER")),
):
    unit = UnitRepository(session).get_by_public_id(unit_id)
    if unit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unit not found")
    try:
        material = _svc.add_material_from_repository(
            session, unit.id, body.title, body.file_id, current_user
        )
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return MaterialRead.model_validate(material)


@router.delete("/materials/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_material(
    material_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN", "TEACHER")),
):
    material = MaterialRepository(session).get_by_public_id(material_id)
    if material is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Material not found")
    try:
        _svc.delete_material(session, material.id, current_user.id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))


@router.post("/materials/{material_id}/publish", status_code=status.HTTP_204_NO_CONTENT)
def publish_material(
    material_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN", "TEACHER")),
):
    material = MaterialRepository(session).get_by_public_id(material_id)
    if material is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Material not found")
    try:
        _svc.publish_material(session, material.id, current_user.id, publish=True)
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))


@router.delete("/materials/{material_id}/publish", status_code=status.HTTP_204_NO_CONTENT)
def unpublish_material(
    material_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN", "TEACHER")),
):
    material = MaterialRepository(session).get_by_public_id(material_id)
    if material is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Material not found")
    try:
        _svc.publish_material(session, material.id, current_user.id, publish=False)
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))


@router.get("/materials/{material_id}/view")
def view_material(
    material_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    material = MaterialRepository(session).get_by_public_id(material_id)
    if material is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Material not found")
    try:
        return _svc.get_material_view_url(session, material.id, current_user.id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))


@router.get("/materials/{material_id}/download")
def download_material(
    material_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN")),
):
    material = MaterialRepository(session).get_by_public_id(material_id)
    if material is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Material not found")
    try:
        return _svc.get_material_download_url(session, material.id, current_user.id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))


@router.get("/materials/{material_id}/annotations")
def get_annotations(
    material_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    try:
        return _svc.get_annotations(session, material_id, current_user.id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))


@router.put("/materials/{material_id}/annotations")
def save_annotations(
    material_id: UUID,
    body: dict[str, Any] = Body(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    highlights = body.get("highlights", [])
    try:
        return _svc.save_annotations(session, material_id, current_user.id, highlights)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
