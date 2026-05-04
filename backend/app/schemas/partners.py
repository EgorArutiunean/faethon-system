from pydantic import BaseModel, field_validator

from app.schemas.common import Timestamped


PARTNER_TYPES = {"customer", "supplier", "both"}


class PartnerBase(BaseModel):
    name: str
    partner_type: str
    code: str | None = None
    tax_id: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    is_active: bool = True

    @field_validator("partner_type")
    @classmethod
    def validate_partner_type(cls, value: str) -> str:
        if value not in PARTNER_TYPES:
            raise ValueError("Invalid partner type")
        return value


class PartnerCreate(PartnerBase):
    pass


class PartnerUpdate(BaseModel):
    name: str | None = None
    partner_type: str | None = None
    code: str | None = None
    tax_id: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    is_active: bool | None = None

    @field_validator("partner_type")
    @classmethod
    def validate_partner_type(cls, value: str | None) -> str | None:
        if value is not None and value not in PARTNER_TYPES:
            raise ValueError("Invalid partner type")
        return value


class PartnerRead(PartnerBase, Timestamped):
    id: int
