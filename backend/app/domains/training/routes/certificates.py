from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlmodel import Session

from app.core.database import get_session
from app.core.permissions import require_roles
from app.core.storage import storage_service, extension_of, safe_content_type
from app.domains.auth.dependencies import get_current_user
from app.domains.auth.models import User
from app.domains.auth.repositories import UserRepository
from app.domains.training.models.training_certificate import TrainingCertificate
from app.domains.training.repositories.certificate_repository import CertificateRepository
from app.domains.training.repositories.enrollment_repository import EnrollmentRepository
from app.domains.training.repositories.program_repository import ProgramRepository
from app.domains.training.schemas.training_certificate import CertificateRead
from app.domains.training.services import TrainingService

router = APIRouter(prefix="/training", tags=["training – certificates"])
_svc = TrainingService()


def _build_certificate_read(session: Session, cert: TrainingCertificate) -> CertificateRead:
    program = ProgramRepository(session).get(cert.program_id)
    return CertificateRead.model_validate(
        cert,
        update={"program_public_id": program.public_id if program else None},
    )


@router.get("/enrollments/{enrollment_id}/check")
def check_completion(
    enrollment_id: UUID,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("ADMIN", "TRAINER", "SUPER_TRAINER")),
):
    try:
        return _svc.check_completion(session, enrollment_id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))


@router.post(
    "/enrollments/{enrollment_id}/certificate",
    response_model=CertificateRead,
    status_code=status.HTTP_201_CREATED,
)
def issue_certificate(
    enrollment_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN", "SUPER_TRAINER")),
):
    try:
        certificate = _svc.issue_certificate(
            session, enrollment_id, current_user.id
        )
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return _build_certificate_read(session, certificate)


@router.get("/certificates/{code}/verify")
def verify_certificate(
    code: str,
    session: Session = Depends(get_session),
):
    certificate = CertificateRepository(session).get_by_code(code)
    if certificate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Certificado no encontrado")
    program = ProgramRepository(session).get(certificate.program_id)
    user = UserRepository(session).get_by_id(certificate.user_id)
    return {
        "valid": True,
        "certificate_code": certificate.certificate_code,
        "issued_at": certificate.issued_at.isoformat(),
        "program_name": program.name if program else None,
        "holder": {
            "first_name": user.first_name if user else None,
            "last_name": user.last_name if user else None,
        },
    }


@router.get("/my-certificates", response_model=list[CertificateRead])
def get_my_certificates(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("TEACHER")),
):
    enrollments = EnrollmentRepository(session).list_by_user(current_user.id)
    cert_repo = CertificateRepository(session)
    result = []
    for enrollment in enrollments:
        cert = cert_repo.get_by_enrollment(enrollment.id)
        if cert is not None:
            result.append(_build_certificate_read(session, cert))
    return result


@router.post("/programs/{program_id}/certificate-template")
def upload_certificate_template(
    program_id: UUID,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("ADMIN", "SUPER_TRAINER")),
):
    # La extensión sale del NOMBRE del archivo, no del content-type que declara
    # el cliente: anclar el content-type a una extensión que el propio cliente
    # eligió sería circular, y guardaba un JPG como .png (plantilla en blanco,
    # sin error visible).
    ext = extension_of(file.filename)
    if ext not in ("png", "jpg", "jpeg"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Solo se permiten PNG o JPG",
        )
    program = ProgramRepository(session).get_by_public_id(program_id)
    if program is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Programa no encontrado")

    key = f"training/certificates/templates/{program.public_id}.{ext}"
    storage_service.upload_file(file.file.read(), key, safe_content_type(key))

    program.certificate_template_key = key
    session.add(program)
    session.commit()

    return {
        "template_url": storage_service.generate_view_url(key, expires_seconds=3600)
    }


@router.get("/programs/{program_id}/certificate-template")
def get_certificate_template(
    program_id: UUID,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    program = ProgramRepository(session).get_by_public_id(program_id)
    if program is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Programa no encontrado")
    if not program.certificate_template_key:
        return {"template_url": None}
    return {
        "template_url": storage_service.generate_view_url(
            program.certificate_template_key, expires_seconds=3600
        )
    }
