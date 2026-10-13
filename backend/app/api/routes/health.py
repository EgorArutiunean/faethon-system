from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/live")
def liveness() -> dict[str, str]:
    return {"status": "alive"}


@lru_cache
def _expected_schema_revision() -> str:
    backend_dir = Path(__file__).resolve().parents[3]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    heads = ScriptDirectory.from_config(config).get_heads()
    if len(heads) != 1:
        raise RuntimeError("Application must have exactly one Alembic head")
    return heads[0]


def _readiness_status(db: Session) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    current_revision = db.execute(
        text("SELECT version_num FROM alembic_version")
    ).scalar_one_or_none()
    expected_revision = _expected_schema_revision()
    if current_revision != expected_revision:
        raise RuntimeError("Database schema revision is not ready")
    return {
        "status": "ready",
        "database": "ok",
        "schema_revision": current_revision,
    }


@router.get("/ready")
def readiness(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        return _readiness_status(db)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service is not ready",
        ) from exc
