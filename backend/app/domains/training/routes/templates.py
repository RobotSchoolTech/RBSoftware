from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlmodel import Session

from app.core.database import get_session
from app.core.permissions import require_roles
from app.core.storage import storage_service
from app.domains.auth.dependencies import get_current_user
from app.domains.auth.models import User
from app.domains.rbac.repositories import UserRoleRepository
from app.domains.training.models.training_template import TrainingTemplate
from app.domains.training.repositories.enrollment_repository import EnrollmentRepository
from app.domains.training.repositories.program_repository import ProgramRepository
from app.domains.training.repositories.template_repository import TemplateRepository
from app.domains.training.schemas.training_template import TemplateRead

router = APIRouter(prefix="/training", tags=["training – templates"])

ALLOWED_EXTENSIONS = ['.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx']
ELEVATED_ROLES = {"ADMIN", "TRAINER", "SUPER_TRAINER"}


@router.get(
    "/programs/{program_id}/templates",
    response_model=list[TemplateRead],
)
def list_templates(
    program_id: UUID,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    program = ProgramRepository(session).get_by_public_id(program_id)
    if program is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Programa no encontrado")
    templates = TemplateRepository(session).list_by_program(program.id)
    return [TemplateRead.model_validate(t) for t in templates]


@router.post(
    "/programs/{program_id}/templates",
    response_model=TemplateRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_template(
    program_id: UUID,
    title: str = Form(...),
    description: str | None = Form(default=None),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN", "TRAINER", "SUPER_TRAINER")),
):
    program = ProgramRepository(session).get_by_public_id(program_id)
    if program is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Programa no encontrado")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Extensión no permitida. Usa: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    file_bytes = await file.read()
    key = f"training/{program.public_id}/templates/{uuid4()}{ext}"
    storage_service.upload_file(
        file_bytes, key, file.content_type or "application/octet-stream"
    )

    template = TrainingTemplate(
        program_id=program.id,
        title=title,
        description=description,
        file_key=key,
        file_name=file.filename or f"template{ext}",
        file_size=len(file_bytes),
        uploaded_by=current_user.id,
    )
    template = TemplateRepository(session).create(template)
    return TemplateRead.model_validate(template)


@router.delete(
    "/programs/templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_template(
    template_id: str,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("ADMIN", "TRAINER", "SUPER_TRAINER")),
):
    repo = TemplateRepository(session)
    template = repo.get_by_public_id(template_id)
    if template is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plantilla no encontrada")
    storage_service.delete_file(template.file_key)
    repo.delete(template)


@router.get("/programs/templates/{template_id}/download")
def download_template(
    template_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    template = TemplateRepository(session).get_by_public_id(template_id)
    if template is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plantilla no encontrada")

    user_roles = UserRoleRepository(session).get_role_names_for_user(current_user.id)
    is_elevated = any(role in ELEVATED_ROLES for role in user_roles)
    if not is_elevated:
        enrolled = EnrollmentRepository(session).is_enrolled(
            current_user.id, template.program_id
        )
        if not enrolled:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "No tienes acceso a esta plantilla",
            )

    url = storage_service.generate_download_url(
        template.file_key, template.file_name, expires_seconds=300
    )
    return {"url": url, "file_name": template.file_name}
