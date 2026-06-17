from pydantic import BaseModel, Field

from app.schemas.common import Timestamped


class RoleRead(Timestamped):
    id: int
    name: str
    description: str | None = None


class UserRead(Timestamped):
    id: int
    email: str
    full_name: str | None = None
    is_active: bool
    role_names: list[str]


class UserCreate(BaseModel):
    email: str
    password: str = Field(min_length=8)
    full_name: str | None = None
    is_active: bool = True
    role_names: list[str]


class UserUpdate(BaseModel):
    email: str | None = None
    password: str | None = Field(default=None, min_length=8)
    full_name: str | None = None
    is_active: bool | None = None
    role_names: list[str] | None = None
