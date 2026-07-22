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
from app.domains.training.repositories.evaluation_repository import EvaluationRepository
from app.domains.training.repositories.submission_repository import SubmissionRepository
from app.domains.training.schemas.composite import QuizSubmitRequest
from app.domains.training.schemas.training_submission import SubmissionRead
from app.domains.training.services import TrainingService

router = APIRouter(prefix="/training", tags=["training – submissions"])
_svc = TrainingService()


class GradeBody(BaseModel):
    score: int
    feedback: str | None = None


@router.post(
    "/evaluations/{evaluation_id}/submit-quiz",
    response_model=SubmissionRead,
)
def submit_quiz(
    evaluation_id: UUID,
    body: QuizSubmitRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("TEACHER")),
):
    try:
        submission = _svc.submit_quiz(
            session, evaluation_id, current_user.id, body.answers
        )
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return SubmissionRead.model_validate(submission)


@router.post(
    "/evaluations/{evaluation_id}/submit-practical",
    response_model=SubmissionRead,
)
async def submit_practical(
    evaluation_id: UUID,
    content: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("TEACHER")),
):
    file_bytes = None
    file_name = None
    if file is not None:
        file_bytes = await file.read()
        if len(file_bytes) > 100 * 1024 * 1024:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "El archivo excede 100 MB"
            )
        file_name = file.filename
    try:
        submission = _svc.submit_practical(
            session,
            evaluation_id,
            current_user.id,
            content,
            file_bytes,
            file_name,
        )
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return SubmissionRead.model_validate(submission)


@router.get(
    "/evaluations/{evaluation_id}/submissions",
    response_model=list[SubmissionRead],
)
def list_submissions(
    evaluation_id: UUID,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("ADMIN", "TRAINER", "SUPER_TRAINER")),
):
    evaluation = EvaluationRepository(session).get_by_public_id(evaluation_id)
    if evaluation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evaluación no encontrada")
    return [
        SubmissionRead.model_validate(s)
        for s in SubmissionRepository(session).get_by_evaluation(evaluation.id)
    ]


@router.get(
    "/evaluations/{evaluation_id}/my-submission",
    response_model=SubmissionRead,
)
def get_my_submission(
    evaluation_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("TEACHER")),
):
    evaluation = EvaluationRepository(session).get_by_public_id(evaluation_id)
    if evaluation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evaluación no encontrada")
    submission = SubmissionRepository(session).get_by_user_and_evaluation(
        current_user.id, evaluation.id
    )
    if submission is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No hay entrega registrada")
    return SubmissionRead.model_validate(submission)


@router.get("/submissions/{submission_id}/view")
def view_submission(
    submission_id: UUID,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("ADMIN", "TRAINER", "SUPER_TRAINER")),
):
    submission = SubmissionRepository(session).get_by_public_id(submission_id)
    if submission is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entrega no encontrada")
    if not submission.file_key:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Esta entrega no tiene archivo")
    # Servido seguro: una entrega .html subida por un docente se entrega como
    # descarga y con content-type anclado, no se ejecuta inline (XSS).
    url = storage_service.generate_view_url(
        submission.file_key, submission.file_name
    )
    return {
        "url": url,
        "file_name": submission.file_name,
    }


@router.post(
    "/submissions/{submission_id}/grade",
    status_code=status.HTTP_204_NO_CONTENT,
)
def grade_submission(
    submission_id: UUID,
    body: GradeBody,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN", "TRAINER", "SUPER_TRAINER")),
):
    try:
        _svc.grade_practical(
            session, submission_id, body.score, body.feedback, current_user.id
        )
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
