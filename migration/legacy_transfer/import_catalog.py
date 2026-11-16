"""Executed inside buy backend by run_transfer.py; stdin is the reviewed plan."""

import hashlib
import json
import sys
from datetime import date
from decimal import Decimal

from app.db.session import engine
from sqlalchemy import Date, MetaData, Numeric, Table, and_, select, text


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=True, default=str).encode()
    ).hexdigest()


DELETE_ORDER = [
    "payment_allocations",
    "cash_operations",
    "payments",
    "warehouse_task_events",
    "warehouse_task_lines",
    "warehouse_tasks",
    "document_revisions",
    "stock_movements",
    "document_lines",
    "documents",
    "stock_balances",
    "prices",
    "user_warehouses",
    "products",
    "partners",
    "warehouses",
]


def run(plan, apply=False):
    if plan["version"] != 2:
        raise ValueError("Unsupported plan version")
    if plan["cleanup_blockers"]:
        raise ValueError("Cleanup has unresolved references")
    if set(plan["cleanup"]) - set(DELETE_ORDER):
        raise ValueError("Unexpected cleanup table")
    if any(
        op["table"] not in ("product_groups", "products", "partners") for op in plan["operations"]
    ):
        raise ValueError("Unexpected insert table")
    plan_hash = digest(plan)
    with engine.connect() as c:
        tx = c.begin()
        try:
            if not apply:
                c.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            else:
                c.execute(text("SET LOCAL lock_timeout = '10s'"))
                c.execute(text("SELECT pg_advisory_xact_lock(20261027, 1)"))
            previous = c.execute(
                text(
                    "SELECT id FROM audit_log WHERE entity_type='legacy_transfer' AND entity_id=:key AND action='apply'"
                ),
                {"key": plan_hash},
            ).first()
            if previous:
                tx.rollback()
                return {"status": "already_applied", "plan_sha256": plan_hash}
            meta = MetaData()
            tables = {t: Table(t, meta, autoload_with=c) for t in plan["target_fingerprints"]}
            if apply:
                # Exclude concurrent edits between comparison and commit.
                for name in sorted(tables):
                    c.execute(text('LOCK TABLE "' + name + '" IN SHARE ROW EXCLUSIVE MODE'))
            for name, expected in plan["target_fingerprints"].items():
                table = tables[name]
                rows = [
                    dict(r)
                    for r in c.execute(
                        select(table).order_by(*table.primary_key.columns)
                    ).mappings()
                ]
                if name == "products":
                    for row in rows:
                        if (
                            row.get("opening_unit_cost") is not None
                            or row.get("opening_cost_date") is not None
                        ):
                            raise ValueError("Existing opening cost requires a new reviewed plan")
                        row.pop("opening_unit_cost", None)
                        row.pop("opening_cost_date", None)
                if digest(rows) != expected:
                    raise ValueError(
                        "Target changed since preparation: "
                        + name
                        + ". Refresh snapshot and review plan."
                    )
            known = {key: ref["id"] for key, ref in plan["links"].items() if "id" in ref}
            seen = set(known)
            for op in plan["operations"]:
                if op["key"] in seen:
                    raise ValueError("Duplicate operation key")
                for value in op["values"].values():
                    if isinstance(value, dict) and "new" in value and value["new"] not in seen:
                        raise ValueError("Forward or missing group reference: " + value["new"])
                seen.add(op["key"])
            if not apply:
                tx.rollback()
                return {
                    "status": "dry_run_ok",
                    "plan_sha256": plan_hash,
                    "summary": plan["summary"],
                    "writes": 0,
                }
            opening_table = Table("inventory_openings", meta, autoload_with=c)
            c.execute(text("LOCK TABLE inventory_openings IN SHARE ROW EXCLUSIVE MODE"))
            if c.execute(select(opening_table.c.id).limit(1)).first():
                raise ValueError("Opening inventory already exists; prepare a new plan")

            def resolve(table, source):
                values = {}
                for col, value in source.items():
                    if isinstance(value, dict):
                        value = value["id"] if "id" in value else known[value["new"]]
                    if value is not None and isinstance(table.c[col].type, Numeric):
                        value = Decimal(str(value))
                    if (
                        value is not None
                        and isinstance(table.c[col].type, Date)
                        and isinstance(value, str)
                    ):
                        value = date.fromisoformat(value)
                    values[col] = value
                return values

            deleted = {}
            for name in DELETE_ORDER:
                rows = plan["cleanup"].get(name, [])
                if not rows:
                    continue
                table = tables[name]
                for row in rows:
                    predicate = and_(*(col == row[col.name] for col in table.primary_key.columns))
                    result = c.execute(table.delete().where(predicate))
                    if result.rowcount != 1:
                        raise ValueError("Cleanup row missing: " + name)
                deleted[name] = len(rows)
            inserted = {}
            for op in plan["operations"]:
                table = tables[op["table"]]
                values = resolve(table, op["values"])
                new_id = c.execute(
                    table.insert().values(**values).returning(table.c.id)
                ).scalar_one()
                known[op["key"]] = new_id
                inserted[op["table"]] = inserted.get(op["table"], 0) + 1
            for op in plan["updates"]:
                table = tables[op["table"]]
                values = resolve(table, op["values"])
                values["updated_at"] = text("CURRENT_TIMESTAMP")
                if (
                    c.execute(
                        table.update().where(table.c.id == op["id"]).values(**values)
                    ).rowcount
                    != 1
                ):
                    raise ValueError("Update target missing")
            for row in plan["opening_lines"]:
                pid = known[row["key"]]
                c.execute(
                    opening_table.insert().values(
                        **resolve(
                            opening_table,
                            {
                                "batch_key": plan_hash,
                                "product_id": pid,
                                "warehouse_id": row["warehouse_id"],
                                "unit_id": row["unit_id"],
                                "effective_date": row["effective_date"],
                                "quantity": row["quantity"],
                                "unit_cost": row["unit_cost"],
                                "amount": row["amount"],
                                "sale_price": row["sale_price"],
                                "currency_code": row["currency_code"],
                                "source_data": json.dumps(row["source_row"], ensure_ascii=True),
                            },
                        )
                    )
                )
                c.execute(
                    tables["prices"]
                    .insert()
                    .values(
                        **resolve(
                            tables["prices"],
                            {
                                "product_id": pid,
                                "currency_id": row["currency_id"],
                                "amount": row["sale_price"],
                                "valid_from": row["effective_date"],
                            },
                        )
                    )
                )
            for row in plan["opening_lines"] + plan["zero_balances"]:
                pid = known[row["key"]] if "key" in row else row["product_id"]
                table = tables["stock_balances"]
                where = and_(table.c.product_id == pid, table.c.warehouse_id == row["warehouse_id"])
                balance = c.execute(select(table).where(where)).mappings().first()
                before = balance["quantity"] if balance else Decimal(0)
                if before != Decimal(row["before_quantity"]):
                    raise ValueError("Stock changed during transfer")
                quantity = Decimal(row["quantity"])
                delta = quantity - before
                if balance:
                    c.execute(
                        table.update()
                        .where(where)
                        .values(quantity=quantity, updated_at=text("CURRENT_TIMESTAMP"))
                    )
                else:
                    c.execute(
                        table.insert().values(
                            product_id=pid, warehouse_id=row["warehouse_id"], quantity=quantity
                        )
                    )
                if delta:
                    c.execute(
                        tables["stock_movements"]
                        .insert()
                        .values(
                            product_id=pid,
                            warehouse_id=row["warehouse_id"],
                            quantity_delta=delta,
                            reason="opening:legacy:" + plan_hash,
                        )
                    )
            # One transaction includes cleanup, inserts, and an idempotency/audit record.
            c.execute(
                text(
                    "INSERT INTO audit_log(entity_type,entity_id,action,details) VALUES ('legacy_transfer',:key,'apply',:details)"
                ),
                {
                    "key": plan_hash,
                    "details": json.dumps(
                        {
                            "inserted": inserted,
                            "deleted": deleted,
                            "updated_products": len(plan["updates"]),
                            "opening": plan["summary"]["opening"],
                            "source_sha256": plan["source_sha256"],
                            "id_map": known,
                        },
                        ensure_ascii=True,
                    ),
                },
            )
            tx.commit()
            return {
                "status": "applied",
                "plan_sha256": plan_hash,
                "inserted": inserted,
                "deleted": deleted,
                "updated_products": len(plan["updates"]),
                "opening": plan["summary"]["opening"],
                "id_map": known,
            }
        except Exception:
            tx.rollback()
            raise


if __name__ == "__main__":
    print(json.dumps(run(json.load(sys.stdin), "--apply" in sys.argv), ensure_ascii=True))
