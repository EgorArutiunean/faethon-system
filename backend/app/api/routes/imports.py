from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.schemas.imports import ImportSummary
from app.services import import_service

router = APIRouter(prefix="/import", tags=["import"])

IMPORT_TYPES = {"products", "partners", "warehouses", "opening-stock", "opening-partner-balances"}


def _check_type(import_type: str) -> None:
    if import_type not in IMPORT_TYPES:
        raise HTTPException(status_code=404, detail="Import type not found")


async def _read_upload(request: Request) -> tuple[bytes, str]:
    content = await request.body()
    filename = request.headers.get("x-filename", "upload.csv")
    return content, filename


@router.get("/templates/{import_type}.xlsx", dependencies=[Depends(require_permission("settings.manage"))])
def template(import_type: str):
    _check_type(import_type)
    content = import_service.build_template(import_type)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{import_type}.xlsx"'},
    )


@router.post("/{import_type}/dry-run", response_model=ImportSummary, dependencies=[Depends(require_permission("settings.manage"))])
async def dry_run(import_type: str, request: Request, db: Session = Depends(get_db)):
    _check_type(import_type)
    content, filename = await _read_upload(request)
    summary, _rows = import_service.validate_import(db, import_type, content, filename)
    return summary


@router.post("/{import_type}/apply", response_model=ImportSummary, dependencies=[Depends(require_permission("settings.manage"))])
async def apply(import_type: str, request: Request, db: Session = Depends(get_db)):
    _check_type(import_type)
    content, filename = await _read_upload(request)
    return import_service.apply_import(db, import_type, content, filename)
