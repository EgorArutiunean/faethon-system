from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import base  # noqa: F401
from app.db.session import SessionLocal
from app.services.auth_seed import seed_auth_defaults


def seed() -> None:
    db = SessionLocal()
    try:
        seed_auth_defaults(db)
        print("E2E users seeded")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
