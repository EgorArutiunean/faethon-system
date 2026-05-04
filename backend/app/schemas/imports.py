from pydantic import BaseModel


class ImportIssue(BaseModel):
    row: int
    field: str | None = None
    message: str


class ImportSummary(BaseModel):
    rows_total: int
    rows_valid: int
    rows_invalid: int
    errors: list[ImportIssue] = []
    warnings: list[ImportIssue] = []
    applied: bool = False
    created: int = 0
    skipped: int = 0
