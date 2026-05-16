from __future__ import annotations

from sqlmodel import Session, select

from app.domains.rbac.models import Role, UserRole
from app.domains.rbac.schemas import UserRoleCreate, UserRoleUpdate


class UserRoleRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, payload: UserRoleCreate) -> UserRole:
        user_role = UserRole.model_validate(payload)
        self.session.add(user_role)
        self.session.commit()
        self.session.refresh(user_role)
        return user_role

    def get_by_id(self, user_role_id: int) -> UserRole | None:
        return self.session.get(UserRole, user_role_id)

    def list(self) -> list[UserRole]:
        statement = select(UserRole).order_by(UserRole.id)
        return list(self.session.exec(statement).all())

    def list_by_user_id(self, user_id: int) -> list[UserRole]:
        statement = select(UserRole).where(UserRole.user_id == user_id)
        return list(self.session.exec(statement).all())

    def update(self, user_role: UserRole, payload: UserRoleUpdate) -> UserRole:
        updates = payload.model_dump(exclude_unset=True)
        for field_name, value in updates.items():
            setattr(user_role, field_name, value)

        self.session.add(user_role)
        self.session.commit()
        self.session.refresh(user_role)
        return user_role

    def delete(self, user_role: UserRole) -> None:
        self.session.delete(user_role)
        self.session.commit()

    def get_role_names_for_user(self, user_id: int) -> list[str]:
        statement = (
            select(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
        )
        return list(self.session.exec(statement).all())

    def set_user_roles(self, user_id: int, role_ids: list[int]) -> None:
        """Reemplaza atómicamente el conjunto de roles del usuario.

        Borra los UserRole existentes que no estén en `role_ids` y agrega los
        que falten. Pensado para sincronizar desde el portal admin (fuente
        única de verdad).
        """
        existing = self.list_by_user_id(user_id)
        existing_ids = {ur.role_id for ur in existing}
        target_ids = set(role_ids)

        for ur in existing:
            if ur.role_id not in target_ids:
                self.session.delete(ur)
        for rid in target_ids - existing_ids:
            self.session.add(UserRole(user_id=user_id, role_id=rid))
        self.session.commit()
