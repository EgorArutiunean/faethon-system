"""Check read-only connectivity to a legacy InterBase/Firebird database."""

from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


def load_config() -> dict[str, str]:
    if load_dotenv:
        load_dotenv()
    return {
        "path": os.getenv("LEGACY_DB_PATH", "").strip(),
        "host": os.getenv("LEGACY_DB_HOST", "").strip(),
        "user": os.getenv("LEGACY_DB_USER", "SYSDBA").strip(),
        "password": os.getenv("LEGACY_DB_PASSWORD", "masterkey"),
        "charset": os.getenv("LEGACY_DB_CHARSET", "WIN1251").strip(),
        "role": os.getenv("LEGACY_DB_ROLE", "").strip(),
        "client": os.getenv("LEGACY_FIREBIRD_CLIENT", "").strip(),
        "confirm_copy": os.getenv("LEGACY_CONFIRM_COPY", "false").strip().lower(),
    }


def validate_config(config: dict[str, str]) -> None:
    if config["confirm_copy"] not in {"1", "true", "yes"}:
        raise SystemExit("Set LEGACY_CONFIRM_COPY=true after pointing LEGACY_DB_PATH to a COPY of BUY.GDB.")
    if not config["path"]:
        raise SystemExit("LEGACY_DB_PATH is required.")
    if not config["host"] and not Path(config["path"]).exists():
        raise SystemExit(f"Local database file was not found: {config['path']}")
    if config["client"] and not Path(config["client"]).exists():
        raise SystemExit(f"LEGACY_FIREBIRD_CLIENT was set, but file was not found: {config['client']}")


def client_message(config: dict[str, str]) -> str:
    if config["client"]:
        return f"Portable Firebird/InterBase client: {config['client']}"
    return "Firebird/InterBase client: system PATH/default loader"


def connect(config: dict[str, str]):
    database = config["path"] if not config["host"] else f"{config['host']}:{config['path']}"
    try:
        import fdb

        kwargs = {
            "dsn": database,
            "user": config["user"],
            "password": config["password"],
            "charset": config["charset"],
        }
        if config["role"]:
            kwargs["role"] = config["role"]
        if config["client"]:
            kwargs["fb_library_name"] = config["client"]
        return fdb.connect(**kwargs)
    except ImportError:
        pass
    except Exception as exc:
        raise RuntimeError(f"fdb connection failed: {exc}") from exc

    try:
        from firebird.driver import connect as fb_connect

        kwargs = {
            "database": database,
            "user": config["user"],
            "password": config["password"],
            "charset": config["charset"],
        }
        if config["role"]:
            kwargs["role"] = config["role"]
        return fb_connect(**kwargs)
    except ImportError as exc:
        raise RuntimeError("Install requirements.txt first.") from exc
    except Exception as exc:
        raise RuntimeError(f"firebird-driver connection failed: {exc}") from exc


def scalar(cursor, sql: str):
    cursor.execute(sql)
    row = cursor.fetchone()
    return row[0] if row else None


def main() -> int:
    config = load_config()
    validate_config(config)
    try:
        con = connect(config)
        cur = con.cursor()
        table_count = scalar(
            cur,
            """
            select count(*)
            from rdb$relations
            where coalesce(rdb$system_flag, 0) = 0
              and rdb$view_blr is null
            """,
        )
        view_count = scalar(
            cur,
            """
            select count(*)
            from rdb$relations
            where coalesce(rdb$system_flag, 0) = 0
              and rdb$view_blr is not null
            """,
        )
        trigger_count = scalar(
            cur,
            "select count(*) from rdb$triggers where coalesce(rdb$system_flag, 0) = 0",
        )
        procedure_count = scalar(cur, "select count(*) from rdb$procedures")
        print("Connection OK")
        print(f"Database: {config['path']}")
        print(client_message(config))
        print(f"User tables: {table_count}")
        print(f"Views: {view_count}")
        print(f"User triggers: {trigger_count}")
        print(f"Procedures: {procedure_count}")
        con.close()
        return 0
    except Exception as exc:
        print("Connection failed.", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        print("Try an older Firebird 1.5/2.0 client or the original InterBase client if this is an old ODS database.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
