from __future__ import annotations

import os
import uuid as uuid_module
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlmodel import Session, or_, select

from app.core.database import get_session
from app.core.permissions import require_roles
from app.core.storage import storage_service
from app.domains.academic.models.school import School, WorkLine
from app.domains.auth.dependencies import get_current_user
from app.domains.auth.models import User
from app.domains.repository.models.repository_file import RepositoryFile
from app.domains.repository.models.repository_folder import RepositoryFolder
from app.domains.repository.models.repository_folder_share import (
    RepositoryFolderShare,
    ShareScopeType,
)
from app.domains.repository.services.visibility import (
    can_see_file,
    can_see_folder,
    get_user_scopes,
)

router = APIRouter()

ALLOWED_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".ppt", ".pptx",
    ".xls", ".xlsx", ".png", ".jpg", ".jpeg",
    ".gif", ".mp4", ".mov", ".avi",
}

# ── Schemas ───────────────────────────────────────────────────────────────────

class ShareRead(BaseModel):
    id: int
    scope_type: str
    work_line: str | None
    school_id: str | None  # public_id del colegio
    school_name: str | None


class FolderRead(BaseModel):
    public_id: str
    name: str
    description: str | None
    parent_id: str | None
    subfolder_count: int
    file_count: int
    created_by_name: str | None
    created_at: datetime
    updated_at: datetime
    shares: list[ShareRead] = []

class FolderCreate(BaseModel):
    name: str
    description: str | None = None
    parent_id: str | None = None

class FolderUpdate(BaseModel):
    name: str | None = None
    description: str | None = None

class FileRead(BaseModel):
    public_id: str
    folder_id: str | None
    name: str
    description: str | None
    file_name: str
    file_size: int | None
    file_type: str | None
    uploaded_by_name: str | None
    created_at: datetime

class BreadcrumbItem(BaseModel):
    public_id: str
    name: str

class FolderDetail(BaseModel):
    public_id: str
    name: str
    description: str | None
    parent_id: str | None
    breadcrumb: list[BreadcrumbItem]
    subfolders: list[FolderRead]
    files: list[FileRead]
    created_by_name: str | None
    created_at: datetime
    updated_at: datetime

# ── Helpers ───────────────────────────────────────────────────────────────────

def _user_name(user_id: int | None, session: Session) -> str | None:
    if user_id is None:
        return None
    u = session.get(User, user_id)
    return f"{u.first_name} {u.last_name}" if u else None

def _parent_public_id(parent_id: int | None, session: Session) -> str | None:
    if parent_id is None:
        return None
    parent = session.get(RepositoryFolder, parent_id)
    return parent.public_id if parent else None

def _share_read(share: RepositoryFolderShare, session: Session) -> ShareRead:
    school_public_id = None
    school_name = None
    if share.school_id is not None:
        school = session.get(School, share.school_id)
        if school is not None:
            school_public_id = str(school.public_id)
            school_name = school.name
    return ShareRead(
        id=share.id,
        scope_type=share.scope_type.value,
        work_line=share.work_line.value if share.work_line is not None else None,
        school_id=school_public_id,
        school_name=school_name,
    )


def _folder_own_shares(folder_id: int, session: Session) -> list[RepositoryFolderShare]:
    return list(
        session.exec(
            select(RepositoryFolderShare).where(
                RepositoryFolderShare.folder_id == folder_id
            )
        ).all()
    )


def _folder_read(folder: RepositoryFolder, session: Session) -> FolderRead:
    subfolder_count = len(
        session.exec(select(RepositoryFolder).where(RepositoryFolder.parent_id == folder.id)).all()
    )
    file_count = len(
        session.exec(select(RepositoryFile).where(RepositoryFile.folder_id == folder.id)).all()
    )
    return FolderRead(
        public_id=folder.public_id,
        name=folder.name,
        description=folder.description,
        parent_id=_parent_public_id(folder.parent_id, session),
        subfolder_count=subfolder_count,
        file_count=file_count,
        created_by_name=_user_name(folder.created_by, session),
        created_at=folder.created_at,
        updated_at=folder.updated_at,
        shares=[_share_read(s, session) for s in _folder_own_shares(folder.id, session)],
    )

def _file_read(f: RepositoryFile, session: Session) -> FileRead:
    folder_public_id = None
    if f.folder_id:
        folder = session.get(RepositoryFolder, f.folder_id)
        folder_public_id = folder.public_id if folder else None
    return FileRead(
        public_id=f.public_id,
        folder_id=folder_public_id,
        name=f.name,
        description=f.description,
        file_name=f.file_name,
        file_size=f.file_size,
        file_type=f.file_type,
        uploaded_by_name=_user_name(f.uploaded_by, session),
        created_at=f.created_at,
    )

def _get_folder(session: Session, public_id: str) -> RepositoryFolder:
    folder = session.exec(
        select(RepositoryFolder).where(RepositoryFolder.public_id == public_id)
    ).first()
    if folder is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Carpeta no encontrada")
    return folder

def _get_file(session: Session, public_id: str) -> RepositoryFile:
    f = session.exec(
        select(RepositoryFile).where(RepositoryFile.public_id == public_id)
    ).first()
    if f is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Archivo no encontrado")
    return f

def _breadcrumb(folder: RepositoryFolder, session: Session) -> list[BreadcrumbItem]:
    crumbs: list[BreadcrumbItem] = []
    current: RepositoryFolder | None = folder
    while current is not None:
        crumbs.append(BreadcrumbItem(public_id=current.public_id, name=current.name))
        current = session.get(RepositoryFolder, current.parent_id) if current.parent_id else None
    crumbs.reverse()
    return crumbs

def _collect_file_keys(folder_id: int, session: Session) -> list[str]:
    keys = [
        f.file_key
        for f in session.exec(select(RepositoryFile).where(RepositoryFile.folder_id == folder_id)).all()
    ]
    for sub in session.exec(select(RepositoryFolder).where(RepositoryFolder.parent_id == folder_id)).all():
        keys.extend(_collect_file_keys(sub.id, session))
    return keys

# ── Folders ───────────────────────────────────────────────────────────────────

@router.get("/folders", response_model=list[FolderRead])
def list_root_folders(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    scopes = get_user_scopes(session, current_user)
    folders = session.exec(
        select(RepositoryFolder).where(RepositoryFolder.parent_id == None)  # noqa: E711
    ).all()
    visible = [f for f in folders if can_see_folder(session, f, current_user, scopes)]
    return [_folder_read(f, session) for f in visible]


@router.get("/folders/{folder_id}", response_model=FolderDetail)
def get_folder(
    folder_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    folder = _get_folder(session, folder_id)
    scopes = get_user_scopes(session, current_user)
    if not can_see_folder(session, folder, current_user, scopes):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Carpeta no encontrada")
    subfolders = session.exec(
        select(RepositoryFolder).where(RepositoryFolder.parent_id == folder.id)
    ).all()
    files = session.exec(
        select(RepositoryFile).where(RepositoryFile.folder_id == folder.id)
    ).all()
    visible_subfolders = [
        sf for sf in subfolders if can_see_folder(session, sf, current_user, scopes)
    ]
    return FolderDetail(
        public_id=folder.public_id,
        name=folder.name,
        description=folder.description,
        parent_id=_parent_public_id(folder.parent_id, session),
        breadcrumb=_breadcrumb(folder, session),
        subfolders=[_folder_read(sf, session) for sf in visible_subfolders],
        files=[_file_read(f, session) for f in files],
        created_by_name=_user_name(folder.created_by, session),
        created_at=folder.created_at,
        updated_at=folder.updated_at,
    )


@router.post("/folders", response_model=FolderRead, status_code=status.HTTP_201_CREATED)
def create_folder(
    data: FolderCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN", "TRAINER", "SUPER_TRAINER")),
):
    parent_id = None
    if data.parent_id:
        parent_id = _get_folder(session, data.parent_id).id
    now = datetime.now(timezone.utc)
    folder = RepositoryFolder(
        name=data.name,
        description=data.description,
        parent_id=parent_id,
        created_by=current_user.id,
        created_at=now,
        updated_at=now,
    )
    session.add(folder)
    session.commit()
    session.refresh(folder)
    return _folder_read(folder, session)


@router.patch("/folders/{folder_id}", response_model=FolderRead)
def update_folder(
    folder_id: str,
    data: FolderUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("ADMIN", "TRAINER", "SUPER_TRAINER")),
):
    folder = _get_folder(session, folder_id)
    if data.name is not None:
        folder.name = data.name
    if data.description is not None:
        folder.description = data.description
    folder.updated_at = datetime.now(timezone.utc)
    session.add(folder)
    session.commit()
    session.refresh(folder)
    return _folder_read(folder, session)


@router.delete("/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_folder(
    folder_id: str,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("ADMIN", "TRAINER", "SUPER_TRAINER")),
):
    folder = _get_folder(session, folder_id)
    for key in _collect_file_keys(folder.id, session):
        storage_service.delete_file(key)
    session.delete(folder)
    session.commit()

# ── Shares (visibilidad por línea / colegio) ──────────────────────────────────

MANAGE_SHARE_ROLES = ("ADMIN", "TRAINER", "SUPER_TRAINER")


class ShareCreate(BaseModel):
    scope_type: str  # "work_line" | "school"
    work_line: str | None = None  # requerido si scope_type == "work_line"
    school_id: str | None = None  # public_id del colegio, requerido si "school"


@router.get("/share-options")
def share_options(
    session: Session = Depends(get_session),
    _: User = Depends(require_roles(*MANAGE_SHARE_ROLES)),
):
    """Opciones para el modal de compartir: líneas de trabajo + colegios."""
    schools = session.exec(select(School).where(School.is_active == True)).all()  # noqa: E712
    return {
        "work_lines": [wl.value for wl in WorkLine],
        "schools": [
            {
                "public_id": str(s.public_id),
                "name": s.name,
                "work_line": s.work_line.value if s.work_line is not None else None,
            }
            for s in schools
        ],
    }


@router.get("/folders/{folder_id}/shares", response_model=list[ShareRead])
def list_folder_shares(
    folder_id: str,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles(*MANAGE_SHARE_ROLES)),
):
    folder = _get_folder(session, folder_id)
    return [_share_read(s, session) for s in _folder_own_shares(folder.id, session)]


@router.post("/folders/{folder_id}/shares", response_model=ShareRead, status_code=status.HTTP_201_CREATED)
def create_folder_share(
    folder_id: str,
    data: ShareCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles(*MANAGE_SHARE_ROLES)),
):
    folder = _get_folder(session, folder_id)

    try:
        scope_type = ShareScopeType(data.scope_type)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "scope_type inválido")

    work_line_val: WorkLine | None = None
    school_db_id: int | None = None

    if scope_type == ShareScopeType.work_line:
        if not data.work_line:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Falta work_line")
        try:
            work_line_val = WorkLine(data.work_line)
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "work_line inválida")
    else:  # school
        if not data.school_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Falta school_id")
        school = session.exec(
            select(School).where(School.public_id == data.school_id)
        ).first()
        if school is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Colegio no encontrado")
        school_db_id = school.id

    existing = session.exec(
        select(RepositoryFolderShare).where(
            RepositoryFolderShare.folder_id == folder.id,
            RepositoryFolderShare.scope_type == scope_type,
            RepositoryFolderShare.work_line == work_line_val,
            RepositoryFolderShare.school_id == school_db_id,
        )
    ).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Esta compartición ya existe")

    share = RepositoryFolderShare(
        folder_id=folder.id,
        scope_type=scope_type,
        work_line=work_line_val,
        school_id=school_db_id,
        created_by=current_user.id,
    )
    session.add(share)
    session.commit()
    session.refresh(share)
    return _share_read(share, session)


@router.delete("/folders/{folder_id}/shares/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_folder_share(
    folder_id: str,
    share_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles(*MANAGE_SHARE_ROLES)),
):
    folder = _get_folder(session, folder_id)
    share = session.get(RepositoryFolderShare, share_id)
    if share is None or share.folder_id != folder.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Compartición no encontrada")
    session.delete(share)
    session.commit()

# ── Files ─────────────────────────────────────────────────────────────────────

@router.post("/files", response_model=FileRead, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str | None = Form(default=None),
    folder_id: str | None = Form(default=None),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_roles("ADMIN", "TRAINER", "SUPER_TRAINER")),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Extensión no permitida: {ext}. Permitidas: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )
    folder_db_id = None
    folder_segment = "root"
    if folder_id:
        folder = _get_folder(session, folder_id)
        folder_db_id = folder.id
        folder_segment = folder.public_id

    file_bytes = await file.read()
    key = f"repository/{folder_segment}/{uuid_module.uuid4()}{ext}"
    storage_service.upload_file(file_bytes, key, file.content_type or "application/octet-stream")

    now = datetime.now(timezone.utc)
    repo_file = RepositoryFile(
        folder_id=folder_db_id,
        name=name,
        description=description,
        file_key=key,
        file_name=file.filename or key.split("/")[-1],
        file_size=len(file_bytes),
        file_type=ext.lstrip(".") or None,
        uploaded_by=current_user.id,
        created_at=now,
        updated_at=now,
    )
    session.add(repo_file)
    session.commit()
    session.refresh(repo_file)
    return _file_read(repo_file, session)


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(
    file_id: str,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("ADMIN", "TRAINER", "SUPER_TRAINER")),
):
    f = _get_file(session, file_id)
    storage_service.delete_file(f.file_key)
    session.delete(f)
    session.commit()


@router.get("/files/{file_id}/download")
def download_file(
    file_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    f = _get_file(session, file_id)
    scopes = get_user_scopes(session, current_user)
    if not can_see_file(session, f.folder_id, f.uploaded_by, current_user, scopes):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Archivo no encontrado")
    url = storage_service.generate_presigned_url(f.file_key, expires_seconds=300, inline=False)
    return {"url": url, "file_name": f.file_name}


@router.get("/files/{file_id}/view")
def view_file(
    file_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    f = _get_file(session, file_id)
    scopes = get_user_scopes(session, current_user)
    if not can_see_file(session, f.folder_id, f.uploaded_by, current_user, scopes):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Archivo no encontrado")
    url = storage_service.generate_presigned_url(f.file_key, expires_seconds=300, inline=True)
    return {"url": url, "file_name": f.file_name, "file_type": f.file_type}


@router.get("/search")
def search(
    q: str = Query(..., min_length=1),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    like = f"%{q}%"
    scopes = get_user_scopes(session, current_user)
    folders = session.exec(
        select(RepositoryFolder).where(
            or_(RepositoryFolder.name.ilike(like), RepositoryFolder.description.ilike(like))
        )
    ).all()
    files = session.exec(
        select(RepositoryFile).where(
            or_(RepositoryFile.name.ilike(like), RepositoryFile.description.ilike(like))
        )
    ).all()
    visible_folders = [
        f for f in folders if can_see_folder(session, f, current_user, scopes)
    ]
    visible_files = [
        f
        for f in files
        if can_see_file(session, f.folder_id, f.uploaded_by, current_user, scopes)
    ]
    return {
        "folders": [_folder_read(f, session) for f in visible_folders],
        "files": [_file_read(f, session) for f in visible_files],
    }


# ── Program ↔ Repository ──────────────────────────────────────────────────────

class AssignFolderRequest(BaseModel):
    folder_id: str


class AssignFileRequest(BaseModel):
    file_id: str


def _get_program_or_404(session: Session, program_public_id: str):
    from app.domains.training.models.training_program import TrainingProgram
    try:
        program_uuid = uuid_module.UUID(program_public_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Programa no encontrado")
    program = session.exec(
        select(TrainingProgram).where(TrainingProgram.public_id == program_uuid)
    ).first()
    if program is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Programa no encontrado")
    return program


def _user_role_names(session: Session, user_id: int) -> set[str]:
    from app.domains.rbac.repositories import UserRoleRepository
    return set(UserRoleRepository(session).get_role_names_for_user(user_id))


def _assert_program_staff(session: Session, program, user: User) -> None:
    roles = _user_role_names(session, user.id)
    if "ADMIN" in roles or "SUPER_TRAINER" in roles:
        return
    if "TRAINER" in roles and program.created_by == user.id:
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Sin permisos sobre este programa")


def _assert_program_access(session: Session, program, user: User) -> None:
    roles = _user_role_names(session, user.id)
    if roles & {"ADMIN", "SUPER_TRAINER"}:
        return
    if "TRAINER" in roles and program.created_by == user.id:
        return
    from app.domains.training.repositories.enrollment_repository import EnrollmentRepository
    enrollments = EnrollmentRepository(session).list_by_user(user.id)
    if any(e.program_id == program.id for e in enrollments):
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "No tienes acceso a este programa")


@router.get("/programs/{program_id}/resources")
def list_program_resources(
    program_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    from app.domains.repository.models.program_repository_folder import ProgramRepositoryFolder
    from app.domains.repository.models.program_repository_file import ProgramRepositoryFile

    program = _get_program_or_404(session, program_id)
    _assert_program_access(session, program, current_user)

    folder_links = session.exec(
        select(ProgramRepositoryFolder).where(ProgramRepositoryFolder.program_id == program.id)
    ).all()
    folders_out = []
    for link in folder_links:
        folder = session.get(RepositoryFolder, link.folder_id)
        if folder is None:
            continue
        file_count = len(
            session.exec(select(RepositoryFile).where(RepositoryFile.folder_id == folder.id)).all()
        )
        folders_out.append({
            "public_id": folder.public_id,
            "name": folder.name,
            "description": folder.description,
            "file_count": file_count,
        })

    file_links = session.exec(
        select(ProgramRepositoryFile).where(ProgramRepositoryFile.program_id == program.id)
    ).all()
    files_out = []
    for link in file_links:
        f = session.get(RepositoryFile, link.file_id)
        if f is None:
            continue
        files_out.append({
            "public_id": f.public_id,
            "name": f.name,
            "file_name": f.file_name,
            "file_size": f.file_size,
            "file_type": f.file_type,
        })

    return {"folders": folders_out, "files": files_out}


@router.post("/programs/{program_id}/assign-folder", status_code=status.HTTP_201_CREATED)
def assign_folder_to_program(
    program_id: str,
    body: AssignFolderRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    from app.domains.repository.models.program_repository_folder import ProgramRepositoryFolder

    program = _get_program_or_404(session, program_id)
    _assert_program_staff(session, program, current_user)
    folder = _get_folder(session, body.folder_id)

    existing = session.exec(
        select(ProgramRepositoryFolder).where(
            ProgramRepositoryFolder.program_id == program.id,
            ProgramRepositoryFolder.folder_id == folder.id,
        )
    ).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "La carpeta ya está asignada a este programa")

    link = ProgramRepositoryFolder(
        program_id=program.id,
        folder_id=folder.id,
        assigned_by=current_user.id,
    )
    session.add(link)
    session.commit()
    return {"message": "Carpeta asignada"}


@router.delete("/programs/{program_id}/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def unassign_folder_from_program(
    program_id: str,
    folder_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    from app.domains.repository.models.program_repository_folder import ProgramRepositoryFolder

    program = _get_program_or_404(session, program_id)
    _assert_program_staff(session, program, current_user)
    folder = _get_folder(session, folder_id)

    link = session.exec(
        select(ProgramRepositoryFolder).where(
            ProgramRepositoryFolder.program_id == program.id,
            ProgramRepositoryFolder.folder_id == folder.id,
        )
    ).first()
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La carpeta no está asignada a este programa")
    session.delete(link)
    session.commit()


@router.post("/programs/{program_id}/assign-file", status_code=status.HTTP_201_CREATED)
def assign_file_to_program(
    program_id: str,
    body: AssignFileRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    from app.domains.repository.models.program_repository_file import ProgramRepositoryFile

    program = _get_program_or_404(session, program_id)
    _assert_program_staff(session, program, current_user)
    f = _get_file(session, body.file_id)

    existing = session.exec(
        select(ProgramRepositoryFile).where(
            ProgramRepositoryFile.program_id == program.id,
            ProgramRepositoryFile.file_id == f.id,
        )
    ).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "El archivo ya está asignado a este programa")

    link = ProgramRepositoryFile(
        program_id=program.id,
        file_id=f.id,
        assigned_by=current_user.id,
    )
    session.add(link)
    session.commit()
    return {"message": "Archivo asignado"}


@router.delete("/programs/{program_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def unassign_file_from_program(
    program_id: str,
    file_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    from app.domains.repository.models.program_repository_file import ProgramRepositoryFile

    program = _get_program_or_404(session, program_id)
    _assert_program_staff(session, program, current_user)
    f = _get_file(session, file_id)

    link = session.exec(
        select(ProgramRepositoryFile).where(
            ProgramRepositoryFile.program_id == program.id,
            ProgramRepositoryFile.file_id == f.id,
        )
    ).first()
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El archivo no está asignado a este programa")
    session.delete(link)
    session.commit()
