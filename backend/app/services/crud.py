from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

ModelT = TypeVar("ModelT")
CreateT = TypeVar("CreateT", bound=BaseModel)
UpdateT = TypeVar("UpdateT", bound=BaseModel)


class CRUDService(Generic[ModelT, CreateT, UpdateT]):
    def __init__(self, model: type[ModelT]) -> None:
        self.model = model

    def list(self, db: Session, *, skip: int = 0, limit: int = 100, search: str | None = None) -> list[ModelT]:
        stmt = select(self.model).offset(skip).limit(limit)
        if search and hasattr(self.model, "name"):
            stmt = select(self.model).where(self.model.name.ilike(f"%{search}%")).offset(skip).limit(limit)
        return list(db.scalars(stmt).all())

    def get(self, db: Session, item_id: int) -> ModelT | None:
        return db.get(self.model, item_id)

    def create(self, db: Session, payload: CreateT) -> ModelT:
        obj = self.model(**payload.model_dump())
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def update(self, db: Session, obj: ModelT, payload: UpdateT) -> ModelT:
        values: dict[str, Any] = payload.model_dump(exclude_unset=True)
        for key, value in values.items():
            setattr(obj, key, value)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def delete(self, db: Session, obj: ModelT) -> None:
        db.delete(obj)
        db.commit()
