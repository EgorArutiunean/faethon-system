"""Export sample rows from important legacy tables."""

from __future__ import annotations

import csv
import os

from export_metadata import clean, output_dir
from export_row_counts import qname
from inspect_firebird import connect, load_config, validate_config


KEY_TABLES = [
    "TOVAR",
    "SKLAD",
    "OSTATOK",
    "NAKLAD",
    "LISTDOK",
    "SODDOK",
    "OPLATA",
    "KASSA_BOOK",
    "PROVODKA",
    "LICO",
    "ACCESS",
]


def table_exists(cur, table: str) -> bool:
    cur.execute(
        """
        select count(*)
        from rdb$relations
        where trim(rdb$relation_name) = ?
          and coalesce(rdb$system_flag, 0) = 0
        """,
        (table,),
    )
    return cur.fetchone()[0] > 0


def column_names(cur, table: str) -> list[str]:
    cur.execute(
        """
        select trim(rdb$field_name)
        from rdb$relation_fields
        where trim(rdb$relation_name) = ?
        order by rdb$field_position
        """,
        (table,),
    )
    return [clean(row[0]) for row in cur.fetchall()]


def main() -> int:
    config = load_config()
    validate_config(config)
    limit = int(os.getenv("LEGACY_SAMPLE_LIMIT", "50"))
    out = output_dir() / "samples"
    out.mkdir(parents=True, exist_ok=True)
    con = connect(config)
    cur = con.cursor()
    for table in KEY_TABLES:
        target = out / f"{table}.csv"
        if not table_exists(cur, table):
            with target.open("w", encoding="utf-8-sig", newline="") as fh:
                writer = csv.writer(fh)
                writer.writerow(["error"])
                writer.writerow([f"Table {table} was not found"])
            print(f"{table}: not found")
            continue
        columns = column_names(cur, table)
        sql = f"select first {limit} * from {qname(table)}"
        try:
            cur.execute(sql)
            rows = cur.fetchall()
            with target.open("w", encoding="utf-8-sig", newline="") as fh:
                writer = csv.writer(fh)
                writer.writerow(columns)
                for row in rows:
                    writer.writerow([clean(value) for value in row])
            print(f"{table}: {len(rows)} sample rows")
        except Exception as exc:
            with target.open("w", encoding="utf-8-sig", newline="") as fh:
                writer = csv.writer(fh)
                writer.writerow(["error"])
                writer.writerow([str(exc)])
            print(f"{table}: ERROR {exc}")
    con.close()
    print(f"Samples exported to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
