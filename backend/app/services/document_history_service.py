import hashlib
import json
from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.document_history import DocumentHistory

SOURCE_SYSTEM = "faeton-buy-legacy"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def prepare(package):
    if (
        package.get("post_movements") is not False
        or package.get("mode") != "historical_export_only"
    ):
        raise ValueError("Only historical packages without posting are accepted")
    digest = package["source_database_sha256"]
    if len(digest) != 64 or any(c not in "0123456789abcdefABCDEF" for c in digest):
        raise ValueError("Invalid source fingerprint")
    docs = package["documents"]
    keys = {d["document_key"] for d in docs}
    if len(keys) != len(docs):
        raise ValueError("Duplicate document keys")
    groups = defaultdict(list)
    line_ids = set()
    for line in package["lines"]:
        if line["document_key"] not in keys or line["source_row_id"] in line_ids:
            raise ValueError("Orphan or duplicate source line")
        line_ids.add(line["source_row_id"])
        for field in ("quantity", "price", "amount"):
            if not Decimal(line[field]).is_finite():
                raise ValueError("Non-finite numeric field")
        groups[line["document_key"]].append(line)
    prepared = []
    for doc in docs:
        lines = groups[doc["document_key"]]
        if not lines or len(lines) != doc["line_count"]:
            raise ValueError("Missing document lines")
        if doc["type"] not in ("incoming", "outgoing"):
            raise ValueError("Unsupported document type")
        source = doc["source"]
        expected = "|".join(source[f] for f in ("DATEDOK_", "VIDDOK_", "NUMDOK_"))
        if expected != doc["document_key"] or source["NUMDOK_"] != doc["number"]:
            raise ValueError("Document identity mismatch")
        amount = Decimal(doc["amount"])
        if not amount.is_finite() or abs(
            sum((Decimal(line["amount"]) for line in lines), Decimal(0)) - amount
        ) > Decimal(".01"):
            raise ValueError("Document amount does not match lines")
        payload = canonical(
            {"header": doc, "lines": sorted(lines, key=lambda line: int(line["line_number"]))}
        )
        prepared.append(
            dict(
                source_system=SOURCE_SYSTEM,
                source_key=doc["document_key"],
                source_database_sha256=digest.lower(),
                payload_sha256=hashlib.sha256(payload.encode()).hexdigest(),
                document_date=date.fromisoformat(doc["date"]),
                document_type=doc["type"],
                number=doc["number"],
                warehouse_code=doc["warehouse_code"],
                partner_name=doc["partner_name"],
                partner_code=doc["partner_code"],
                payload=payload,
            )
        )
    return prepared


def import_history(db: Session, package: dict, apply: bool = False):
    """Caller owns transaction. This function writes only document_history."""
    prepared = prepare(package)
    if apply and db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(44440020)"))
    existing = {
        r.source_key: r
        for r in db.scalars(
            select(DocumentHistory).where(DocumentHistory.source_system == SOURCE_SYSTEM)
        ).all()
    }
    additions = []
    for row in prepared:
        old = existing.get(row["source_key"])
        if old:
            if (
                old.payload_sha256 != row["payload_sha256"]
                or hashlib.sha256(old.payload.encode()).hexdigest() != row["payload_sha256"]
            ):
                raise ValueError(
                    "Historical document changed; explicit review required: " + row["source_key"]
                )
        else:
            additions.append(row)
    if apply:
        db.add_all(DocumentHistory(**row) for row in additions)
        db.flush()
    return {
        "status": "applied" if apply else "dry_run_ok",
        "added": len(additions),
        "unchanged": len(prepared) - len(additions),
        "documents": len(prepared),
        "lines": len(package["lines"]),
        "operational_writes": 0,
    }
