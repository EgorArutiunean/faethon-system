from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenRead(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CurrentUserRead(BaseModel):
    id: int
    email: str
    full_name: str | None = None
    role_names: list[str]
    permissions: list[str]
    warehouse_ids: list[int] = Field(default_factory=list)
    warehouse_names: list[str] = Field(default_factory=list)
