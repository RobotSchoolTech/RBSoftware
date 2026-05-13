from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session

from app.core.database import get_session
from app.core.permissions import require_roles
from app.domains.auth.dependencies import get_current_user
from app.domains.academic.repositories.rubric_repository import RubricRepository
from app.domains.auth.models import User
from app.domains.rbac.repositories import UserRoleRepository
from app.domains.training.models.training_evaluation import TrainingEvaluation
from app.domains.training.repositories.evaluation_repository import EvaluationRepository
from app.domains.training.repositories.module_repository import ModuleRepository
from app.domains.training.repositories.quiz_question_repository import QuizQuestionRepository
from app.domains.training.schemas.training_evaluation import (
    EvaluationCreate,
    EvaluationRead,
    EvaluationUpdate,
)
from app.domains.training.schemas.training_quiz_question import (
    QuizQuestionCreate,
    QuizQuestionRead,
    QuizQuestionUpdate,
)
from app.domains.training.services import TrainingService

router = APIRouter(prefix="/training", tags=["training – evaluations"])
_svc = TrainingService()


@router.get(
    "/modules/{module_id}/evaluations", response_model=list[EvaluationRead]
)
def list_evaluations(
    module_id: UUID,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    module = ModuleRepository(session).get_by_public_id(module_id)
    if module is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Módulo no encontrado")
    return [
        _svc.build_evaluation_read(session, e)
        for e in EvaluationRepository(session).list_by_module(module.id)
    ]


@router.post(
    "/modules/{module_id}/evaluations",
    response_model=EvaluationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_evaluation(
    module_id: UUID,
    data: EvaluationCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN", "TRAINER", "SUPER_TRAINER")),
):
    try:
        evaluation = _svc.create_evaluation(
            session, module_id, data, current_user.id
        )
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
    return _svc.build_evaluation_read(session, evaluation)


@router.patch("/evaluations/{evaluation_id}", response_model=EvaluationRead)
def update_evaluation(
    evaluation_id: UUID,
    data: EvaluationUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN", "TRAINER", "SUPER_TRAINER")),
):
    try:
        updated = _svc.update_evaluation(
            session, evaluation_id, data, current_user.id
        )
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return _svc.build_evaluation_read(session, updated)


class PublishEvalRequest(BaseModel):
    publish: bool = True


@router.post(
    "/evaluations/{evaluation_id}/publish",
    status_code=status.HTTP_204_NO_CONTENT,
)
def publish_evaluation(
    evaluation_id: UUID,
    body: PublishEvalRequest = PublishEvalRequest(),
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("ADMIN", "TRAINER", "SUPER_TRAINER")),
):
    evaluation = EvaluationRepository(session).get_by_public_id(evaluation_id)
    if evaluation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evaluación no encontrada")
    evaluation.is_published = body.publish
    session.add(evaluation)
    session.commit()


@router.get("/evaluations/{evaluation_id}/questions")
def list_questions(
    evaluation_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    evaluation = EvaluationRepository(session).get_by_public_id(evaluation_id)
    if evaluation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evaluación no encontrada")
    questions = QuizQuestionRepository(session).list_by_evaluation(evaluation.id)

    role_names = UserRoleRepository(session).get_role_names_for_user(current_user.id)
    show_answers = "ADMIN" in role_names or "TRAINER" in role_names

    result = []
    for q in questions:
        item = QuizQuestionRead.model_validate(q).model_dump()
        if not show_answers:
            item.pop("correct_option", None)
        result.append(item)
    return result


@router.post(
    "/evaluations/{evaluation_id}/questions",
    response_model=QuizQuestionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_question(
    evaluation_id: UUID,
    data: QuizQuestionCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN", "TRAINER", "SUPER_TRAINER")),
):
    try:
        question = _svc.create_quiz_question(
            session, evaluation_id, data, current_user.id
        )
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return QuizQuestionRead.model_validate(question)


@router.delete(
    "/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_question(
    question_id: UUID,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("ADMIN", "TRAINER", "SUPER_TRAINER")),
):
    repo = QuizQuestionRepository(session)
    question = repo.get_by_public_id(question_id)
    if question is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pregunta no encontrada")
    evaluation = session.get(TrainingEvaluation, question.evaluation_id)
    repo.delete(question)
    if evaluation:
        remaining = repo.list_by_evaluation(evaluation.id)
        evaluation.max_score = sum(q.points for q in remaining)
        session.add(evaluation)
        session.commit()


class _RubricLevelBody(BaseModel):
    title: str
    description: str | None = None
    points: int


class _RubricCriteriaBody(BaseModel):
    title: str
    description: str | None = None
    weight: int = 1
    levels: list[_RubricLevelBody] = []


class RubricBody(BaseModel):
    title: str
    description: str | None = None
    criteria: list[_RubricCriteriaBody] = []


@router.get("/evaluations/{evaluation_id}/rubric")
def get_evaluation_rubric(
    evaluation_id: UUID,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    evaluation = EvaluationRepository(session).get_by_public_id(evaluation_id)
    if evaluation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evaluación no encontrada")
    repo = RubricRepository(session)
    rubric = repo.get_by_evaluation(evaluation.id)
    if rubric is None:
        return None
    return repo.get_full(rubric.id)


@router.put("/evaluations/{evaluation_id}/rubric")
def upsert_evaluation_rubric(
    evaluation_id: UUID,
    body: RubricBody,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("ADMIN", "TRAINER", "SUPER_TRAINER")),
):
    evaluation = EvaluationRepository(session).get_by_public_id(evaluation_id)
    if evaluation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evaluación no encontrada")
    repo = RubricRepository(session)
    rubric = repo.upsert_full(body.model_dump(), evaluation_id=evaluation.id)
    return repo.get_full(rubric.id)
