from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, select

from app.domains.academic.models.lms_material import LmsMaterial
from app.domains.academic.schemas.lms_material import MaterialCreate, MaterialUpdate


class MaterialRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        unit_id: int,
        payload: MaterialCreate,
        file_key: str | None = None,
        file_name: str | None = None,
    ) -> LmsMaterial:
        update = {"unit_id": unit_id}
        if file_key is not None:
            update["file_key"] = file_key
        if file_name is not None:
            update["file_name"] = file_name
        material = LmsMaterial.model_validate(payload, update=update)
        self.session.add(material)
        self.session.commit()
        self.session.refresh(material)
        return material

    def get_by_id(self, material_id: int) -> LmsMaterial | None:
        return self.session.get(LmsMaterial, material_id)

    def get_by_public_id(self, public_id: UUID) -> LmsMaterial | None:
        stmt = select(LmsMaterial).where(LmsMaterial.public_id == public_id)
        return self.session.exec(stmt).first()

    def list_by_unit(
        self, unit_id: int, published_only: bool = False
    ) -> list[LmsMaterial]:
        stmt = select(LmsMaterial).where(LmsMaterial.unit_id == unit_id)
        if published_only:
            stmt = stmt.where(LmsMaterial.is_published.is_(True))
        stmt = stmt.order_by(LmsMaterial.order_index)
        return list(self.session.exec(stmt).all())

    def update(self, material: LmsMaterial, payload: MaterialUpdate) -> LmsMaterial:
        updates = payload.model_dump(exclude_unset=True)
        for field_name, value in updates.items():
            setattr(material, field_name, value)
        self.session.add(material)
        self.session.commit()
        self.session.refresh(material)
        return material

    def publish(self, material: LmsMaterial) -> LmsMaterial:
        material.is_published = True
        self.session.add(material)
        self.session.commit()
        self.session.refresh(material)
        return material

    def unpublish(self, material: LmsMaterial) -> LmsMaterial:
        material.is_published = False
        self.session.add(material)
        self.session.commit()
        self.session.refresh(material)
        return material

    def delete(self, material: LmsMaterial) -> None:
        self.session.delete(material)
        self.session.commit()
