"""Export legacy Firebird/InterBase metadata to CSV and SQL files."""

from __future__ import annotations

import csv
import os
from pathlib import Path

from inspect_firebird import connect, load_config, validate_config


TYPE_MAP = {
    7: "SMALLINT",
    8: "INTEGER",
    9: "QUAD",
    10: "FLOAT",
    12: "DATE",
    13: "TIME",
    14: "CHAR",
    16: "BIGINT/NUMERIC",
    27: "DOUBLE",
    35: "TIMESTAMP",
    37: "VARCHAR",
    40: "CSTRING",
    45: "BLOB_ID",
    261: "BLOB",
}


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def output_dir() -> Path:
    raw = os.getenv("LEGACY_OUTPUT_DIR", "migration/legacy_schema")
    path = Path(raw)
    if not path.is_absolute():
        path = project_root() / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def clean(value):
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if hasattr(value, "read"):
        data = value.read()
        if isinstance(data, bytes):
            return data.decode("utf-8", errors="replace").strip()
        return str(data).strip()
    return str(value).strip()


def write_csv(path: Path, headers: list[str], rows) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(headers)
        for row in rows:
            writer.writerow([clean(value) for value in row])


def write_blob_sql(path: Path, title: str, rows, name_index: int, source_index: int) -> None:
    with path.open("w", encoding="utf-8") as fh:
        fh.write(f"-- {title}\n")
        for row in rows:
            name = clean(row[name_index])
            source = clean(row[source_index])
            fh.write("\n")
            fh.write(f"-- {name}\n")
            if source:
                fh.write(source.rstrip())
                if not source.rstrip().endswith(";"):
                    fh.write(";")
                fh.write("\n")
            else:
                fh.write("-- No source text available in metadata.\n")


def fetch_all(cur, sql: str):
    cur.execute(sql)
    return cur.fetchall()


def export_tables(cur, out: Path) -> list[str]:
    rows = fetch_all(
        cur,
        """
        select
            trim(r.rdb$relation_name) as relation_name,
            case when r.rdb$view_blr is null then 'TABLE' else 'VIEW' end as relation_type,
            coalesce(r.rdb$system_flag, 0) as system_flag,
            r.rdb$description
        from rdb$relations r
        where coalesce(r.rdb$system_flag, 0) = 0
        order by r.rdb$relation_name
        """,
    )
    write_csv(out / "tables.csv", ["relation_name", "relation_type", "system_flag", "description"], rows)
    return [clean(row[0]) for row in rows if clean(row[1]) == "TABLE"]


def export_columns(cur, out: Path) -> None:
    rows = fetch_all(
        cur,
        """
        select
            trim(rf.rdb$relation_name) as relation_name,
            trim(rf.rdb$field_name) as column_name,
            rf.rdb$field_position as ordinal_position,
            trim(rf.rdb$field_source) as field_source,
            f.rdb$field_type,
            f.rdb$field_sub_type,
            f.rdb$field_length,
            f.rdb$field_precision,
            f.rdb$field_scale,
            f.rdb$character_length,
            case when rf.rdb$null_flag = 1 or f.rdb$null_flag = 1 then 'NO' else 'YES' end as is_nullable,
            rf.rdb$default_source,
            f.rdb$default_source,
            f.rdb$computed_source,
            rf.rdb$description
        from rdb$relation_fields rf
        join rdb$fields f on f.rdb$field_name = rf.rdb$field_source
        join rdb$relations r on r.rdb$relation_name = rf.rdb$relation_name
        where coalesce(r.rdb$system_flag, 0) = 0
        order by rf.rdb$relation_name, rf.rdb$field_position
        """,
    )
    enhanced = []
    for row in rows:
        values = list(row)
        values.insert(5, TYPE_MAP.get(row[4], f"UNKNOWN_{row[4]}"))
        enhanced.append(values)
    write_csv(
        out / "columns.csv",
        [
            "relation_name",
            "column_name",
            "ordinal_position",
            "field_source",
            "field_type_code",
            "field_type_name",
            "field_sub_type",
            "field_length",
            "field_precision",
            "field_scale",
            "character_length",
            "is_nullable",
            "relation_default",
            "field_default",
            "computed_source",
            "description",
        ],
        enhanced,
    )


def export_indexes(cur, out: Path) -> None:
    rows = fetch_all(
        cur,
        """
        select
            trim(i.rdb$relation_name) as relation_name,
            trim(i.rdb$index_name) as index_name,
            i.rdb$unique_flag,
            i.rdb$index_inactive,
            i.rdb$index_type,
            trim(s.rdb$field_name) as field_name,
            s.rdb$field_position,
            trim(rc.rdb$constraint_type) as constraint_type,
            trim(rc.rdb$constraint_name) as constraint_name,
            trim(ref.rdb$const_name_uq) as referenced_constraint
        from rdb$indices i
        left join rdb$index_segments s on s.rdb$index_name = i.rdb$index_name
        left join rdb$relation_constraints rc on rc.rdb$index_name = i.rdb$index_name
        left join rdb$ref_constraints ref on ref.rdb$constraint_name = rc.rdb$constraint_name
        join rdb$relations r on r.rdb$relation_name = i.rdb$relation_name
        where coalesce(r.rdb$system_flag, 0) = 0
        order by i.rdb$relation_name, i.rdb$index_name, s.rdb$field_position
        """,
    )
    write_csv(
        out / "indexes.csv",
        [
            "relation_name",
            "index_name",
            "unique_flag",
            "index_inactive",
            "index_type",
            "field_name",
            "field_position",
            "constraint_type",
            "constraint_name",
            "referenced_constraint",
        ],
        rows,
    )


def export_triggers(cur, out: Path) -> None:
    rows = fetch_all(
        cur,
        """
        select
            trim(t.rdb$trigger_name) as trigger_name,
            trim(t.rdb$relation_name) as relation_name,
            t.rdb$trigger_type,
            t.rdb$trigger_sequence,
            t.rdb$trigger_inactive,
            t.rdb$trigger_source
        from rdb$triggers t
        where coalesce(t.rdb$system_flag, 0) = 0
        order by t.rdb$relation_name, t.rdb$trigger_name
        """,
    )
    write_blob_sql(out / "triggers.sql", "User triggers", rows, 0, 5)


def export_procedures(cur, out: Path) -> None:
    rows = fetch_all(
        cur,
        """
        select
            trim(p.rdb$procedure_name) as procedure_name,
            p.rdb$procedure_inputs,
            p.rdb$procedure_outputs,
            p.rdb$procedure_source
        from rdb$procedures p
        order by p.rdb$procedure_name
        """,
    )
    write_blob_sql(out / "procedures.sql", "Stored procedures", rows, 0, 3)


def main() -> int:
    config = load_config()
    validate_config(config)
    out = output_dir()
    con = connect(config)
    cur = con.cursor()
    export_tables(cur, out)
    export_columns(cur, out)
    export_indexes(cur, out)
    export_triggers(cur, out)
    export_procedures(cur, out)
    con.close()
    print(f"Metadata exported to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
