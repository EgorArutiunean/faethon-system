import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.security import hash_password
from app.db import base as db_base  # noqa: F401
from app.db.session import SessionLocal
from app.models.identity import User
from app.services.auth_seed import seed_permissions_and_roles


def bootstrap_admin() -> None:
    email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "")
    full_name = os.environ.get("BOOTSTRAP_ADMIN_FULL_NAME", "Initial Administrator").strip()

    if not email:
        raise RuntimeError("BOOTSTRAP_ADMIN_EMAIL is required")
    if len(password) < 12:
        raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD must be at least 12 characters")

    db = SessionLocal()
    try:
        roles = seed_permissions_and_roles(db)
        existing = db.scalar(select(User).where(User.username == email))
        if existing is not None:
            raise RuntimeError(
                "Administrator already exists; bootstrap does not reset existing accounts"
            )

        admin = User(
            username=email,
            full_name=full_name or None,
            hashed_password=hash_password(password),
            is_active=True,
            must_change_password=True,
        )
        admin.roles = [roles["admin"]]
        db.add(admin)
        db.commit()
        print(f"Initial administrator created: {email}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    bootstrap_admin()
