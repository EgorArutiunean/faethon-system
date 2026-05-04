"""Export row counts for all user tables."""

from __future__ import annotations

import csv
from pathlib import Path

from export_metadata import clean, output_dir
from inspect_firebird import connect, load_config, validate_config


def qname(name: str) -> str:
    escaped = name.replace('"', '""')
    return f'"{escaped}"'


def user_tables(cur) -> list[str]:
    cur.execute(
        """
        select trim(rdb$relation_name)
        from rdb$relations
        where coalesce(rdb$system_flag, 0) = 0
          and rdb$view_blr is null
        order by rdb$relation_name
        """
    )
    return [clean(row[0]) for row in cur.fetchall()]


def main() -> int:
    config = load_config()
    validate_config(config)
    out = output_dir()
    con = connect(config)
    cur = con.cursor()
    results = []
    for table in user_tables(cur):
        try:
            cur.execute(f"select count(*) from {qname(table)}")
            count = cur.fetchone()[0]
            results.append((table, count, ""))
            print(f"{table}: {count}")
        except Exception as exc:
            results.append((table, "", str(exc)))
            print(f"{table}: ERROR {exc}")
    with (out / "row_counts.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(["table_name", "row_count", "error"])
        writer.writerows(results)
    con.close()
    print(f"Row counts exported to {Path(out / 'row_counts.csv')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
