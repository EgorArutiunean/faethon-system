from pydantic import BaseModel

from app.schemas.common import Timestamped


class WarehouseBase(BaseModel):
    code: str | None = None
    name: str
    address: str | None = None


class WarehouseCreate(WarehouseBase):
    pass


class WarehouseUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    address: str | None = None


class WarehouseRead(WarehouseBase, Timestamped):
    id: int
