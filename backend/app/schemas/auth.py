from pydantic import BaseModel


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
