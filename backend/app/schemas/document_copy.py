from datetime import date

from pydantic import BaseModel, ConfigDict


class DocumentCopy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_date: date | None = None
