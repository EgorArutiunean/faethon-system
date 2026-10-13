from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenRead(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=12)


class CurrentUserRead(BaseModel):
    id: int
    email: str
    full_name: str | None = None
    role_names: list[str]
    permissions: list[str]
    must_change_password: bool
    warehouse_ids: list[int] = Field(default_factory=list)
    warehouse_names: list[str] = Field(default_factory=list)
