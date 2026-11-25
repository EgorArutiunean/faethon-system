from copy import deepcopy

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.models.document_history import DocumentHistory
from app.services.document_history_service import import_history


def test_archived_invoice_import_is_idempotent_and_rejects_changed_payload():
    engine = create_engine("sqlite://")
    DocumentHistory.__table__.create(engine)
    key = "2020-01-01|1|TEST"
    package = {
        "mode": "historical_export_only",
        "post_movements": False,
        "source_database_sha256": "a" * 64,
        "documents": [
            {
                "document_key": key,
                "line_count": 1,
                "type": "incoming",
                "source": {"DATEDOK_": "2020-01-01", "VIDDOK_": "1", "NUMDOK_": "TEST"},
                "number": "TEST",
                "date": "2020-01-01",
                "amount": "10.00",
                "warehouse_code": "TEST",
                "partner_name": "Synthetic supplier",
                "partner_code": "TEST",
            }
        ],
        "lines": [
            {
                "document_key": key,
                "source_row_id": 1,
                "line_number": 1,
                "quantity": "2",
                "price": "5.00",
                "amount": "10.00",
            }
        ],
    }
    count = select(func.count()).select_from(DocumentHistory)
    with Session(engine) as db:
        assert import_history(db, package)["added"] == 1
        assert db.scalar(count) == 0
        assert import_history(db, package, apply=True)["added"] == 1
        db.commit()
        assert import_history(db, package, apply=True)["unchanged"] == 1
        changed = deepcopy(package)
        changed["documents"][0]["partner_name"] = "Changed supplier"
        with pytest.raises(ValueError, match="Historical document changed"):
            import_history(db, changed, apply=True)
        assert db.scalar(count) == 1
    engine.dispose()
