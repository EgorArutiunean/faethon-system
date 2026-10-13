from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.imports import ImportSummary
from app.services import import_service

router = APIRouter(prefix="/import", tags=["import"])

IMPORT_TYPES = {"products", "partners", "warehouses", "opening-stock", "opening-partner-balances"}


def _check_type(import_type: str) -> None:
    if import_type not in IMPORT_TYPES:
        raise HTTPException(status_code=404, detail="Import type not found")


async def _read_upload(request: Request) -> tuple[bytes, str]:
    max_bytes = get_settings().import_max_bytes
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > max_bytes:
                raise HTTPException(status_code=413, detail="Import file is too large")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Content-Length header") from None

    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > max_bytes:
            raise HTTPException(status_code=413, detail="Import file is too large")
        chunks.append(chunk)
    content = b"".join(chunks)
    filename = request.headers.get("x-filename", "upload.csv")
    return content, filename


def _validate(db: Session, import_type: str, content: bytes, filename: str):
    try:
        return import_service.validate_import(db, import_type, content, filename)
    except import_service.ImportLimitError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except import_service.ImportFormatError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/templates/{import_type}.xlsx", dependencies=[Depends(require_permission("settings.manage"))]
)
def template(import_type: str):
    _check_type(import_type)
    content = import_service.build_template(import_type)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{import_type}.xlsx"'},
    )


@router.post(
    "/{import_type}/dry-run",
    response_model=ImportSummary,
    dependencies=[Depends(require_permission("settings.manage"))],
)
async def dry_run(import_type: str, request: Request, db: Session = Depends(get_db)):
    _check_type(import_type)
    content, filename = await _read_upload(request)
    summary, _rows = _validate(db, import_type, content, filename)
    return summary


@router.post(
    "/{import_type}/apply",
    response_model=ImportSummary,
    dependencies=[Depends(require_permission("settings.manage"))],
)
async def apply(import_type: str, request: Request, db: Session = Depends(get_db)):
    _check_type(import_type)
    content, filename = await _read_upload(request)
    try:
        return import_service.apply_import(db, import_type, content, filename)
    except import_service.ImportLimitError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except import_service.ImportFormatError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
