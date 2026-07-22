from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.database import get_session
from app.domains.academic.repositories import AssignmentRepository, UnitRepository
from app.domains.academic.schemas import (
    AssignmentCreate, AssignmentRead, AssignmentUpdate,
    SubmissionWithStudent,
)
from app.domains.academic.services import AcademicService
from app.core.permissions import require_roles
from app.domains.auth.dependencies import get_current_user
from app.domains.auth.models import User
from app.domains.auth.schemas.user import UserRead

router = APIRouter(prefix="/academic", tags=["academic – assignments"])
_svc = AcademicService()


@router.get("/units/{unit_id}/assignments", response_model=list[AssignmentRead])
def list_assignments(
    unit_id: UUID,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    unit = UnitRepository(session).get_by_public_id(unit_id)
    if unit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unit not found")
    return [
        AssignmentRead.model_validate(a)
        for a in AssignmentRepository(session).list_by_unit(unit.id)
    ]


@router.post(
    "/units/{unit_id}/assignments",
    response_model=AssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_assignment(
    unit_id: UUID,
    data: AssignmentCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN", "TEACHER")),
):
    unit = UnitRepository(session).get_by_public_id(unit_id)
    if unit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unit not found")
    try:
        assignment = _svc.create_assignment(
            session, unit.id, data, current_user.id
        )
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
    return AssignmentRead.model_validate(assignment)


@router.patch("/assignments/{assignment_id}", response_model=AssignmentRead)
def update_assignment(
    assignment_id: UUID,
    data: AssignmentUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN", "TEACHER")),
):
    assignment = AssignmentRepository(session).get_by_public_id(assignment_id)
    if assignment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assignment not found")
    try:
        updated = _svc.update_assignment(session, assignment.id, data, current_user.id)
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
    return AssignmentRead.model_validate(updated)


@router.delete("/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assignment(
    assignment_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN", "TEACHER")),
):
    assignment = AssignmentRepository(session).get_by_public_id(assignment_id)
    if assignment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assignment not found")
    try:
        _svc.delete_assignment(session, assignment.id, current_user.id)
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))


@router.post(
    "/assignments/{assignment_id}/publish",
    status_code=status.HTTP_204_NO_CONTENT,
)
def publish_assignment(
    assignment_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN", "TEACHER")),
):
    assignment = AssignmentRepository(session).get_by_public_id(assignment_id)
    if assignment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assignment not found")
    try:
        _svc.publish_assignment(
            session, assignment.id, current_user.id, publish=True
        )
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))


@router.delete(
    "/assignments/{assignment_id}/publish",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unpublish_assignment(
    assignment_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN", "TEACHER")),
):
    assignment = AssignmentRepository(session).get_by_public_id(assignment_id)
    if assignment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assignment not found")
    try:
        _svc.publish_assignment(
            session, assignment.id, current_user.id, publish=False
        )
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))


@router.get(
    "/assignments/{assignment_id}/submissions",
    response_model=list[SubmissionWithStudent],
)
def get_submissions(
    assignment_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN", "TEACHER")),
):
    assignment = AssignmentRepository(session).get_by_public_id(assignment_id)
    if assignment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assignment not found")
    try:
        rows = _svc.get_assignment_submissions(session, assignment.id, current_user.id)
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
    return [
        SubmissionWithStudent(
            public_id=sub.public_id,
            content=sub.content,
            file_name=sub.file_name,
            status=sub.status,
            score=sub.score,
            feedback=sub.feedback,
            submitted_at=sub.submitted_at,
            graded_at=sub.graded_at,
            created_at=sub.created_at,
            updated_at=sub.updated_at,
            student=UserRead.model_validate(user),
        )
        for sub, user in rows
    ]
