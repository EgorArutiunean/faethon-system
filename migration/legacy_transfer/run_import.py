"""Run the reviewed legacy transfer against this checkout's local Compose stack."""

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = Path(__file__).with_name("import_catalog.py")
HISTORY = """
import json
import sys

from sqlalchemy import inspect

from app.db.session import SessionLocal, engine
from app.services.document_history_service import import_history, prepare

package = json.load(sys.stdin)
apply = "--apply" in sys.argv
if not inspect(engine).has_table("document_history") and not apply:
    documents = prepare(package)
    result = {
        "status": "dry_run_ok",
        "schema_required": True,
        "documents": len(documents),
        "lines": len(package["lines"]),
    }
else:
    with SessionLocal.begin() as session:
        result = import_history(session, package, apply)
print(json.dumps(result))
"""


def compose(*args, **kwargs):
    return subprocess.run(["docker", "compose", *args], cwd=ROOT, check=True, **kwargs)


def run_import(code, payload, apply=False):
    command = ["exec", "-T"]
    if not apply:
        command += ["-e", "PGOPTIONS=-c default_transaction_read_only=on"]
    command += ["backend", "python", "-c", code]
    if apply:
        command.append("--apply")
    result = json.loads(compose(*command, input=payload, stdout=subprocess.PIPE).stdout)
    result.pop("id_map", None)
    return result


def backup_database(directory):
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = directory / f"before_legacy_transfer_{timestamp}.dump"
    with backup.open("xb") as output:
        compose(
            "exec",
            "-T",
            "postgres",
            "sh",
            "-c",
            'pg_dump -Fc -U "$POSTGRES_USER" -d "$POSTGRES_DB"',
            stdout=output,
        )
    with backup.open("rb") as source:
        compose("exec", "-T", "postgres", "pg_restore", "--file=/dev/null", stdin=source)
    print(f"Verified backup: {backup}", flush=True)


def verify_local_database():
    database = (
        compose("exec", "-T", "postgres", "printenv", "POSTGRES_DB", stdout=subprocess.PIPE)
        .stdout.decode()
        .strip()
    )
    probe = """
import socket
import sys

from sqlalchemy import text

from app.db.session import engine

with engine.connect() as connection:
    name, host = connection.execute(
        text("SELECT current_database(), host(inet_server_addr())")
    ).one()
if name != sys.argv[1] or host != socket.gethostbyname("postgres"):
    raise SystemExit("Backend is not connected to the local Compose PostgreSQL service")
"""
    compose(
        "exec",
        "-T",
        "-e",
        "PGOPTIONS=-c default_transaction_read_only=on",
        "backend",
        "python",
        "-c",
        probe,
        database,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--apply", action="store_true")
    options = parser.parse_args()
    if options.apply and not options.backup_dir:
        parser.error("--apply requires --backup-dir")

    catalog_code = CATALOG.read_text(encoding="utf-8")
    plan = options.plan.read_bytes()
    history = options.history.read_bytes()
    verify_local_database()
    checks = {
        "catalog": run_import(catalog_code, plan),
        "history": run_import(HISTORY, history),
    }
    print(json.dumps(checks, ensure_ascii=True, indent=2), flush=True)
    if not options.apply:
        return
    backup_database(options.backup_dir)
    compose("exec", "-T", "backend", "alembic", "upgrade", "head")
    catalog_result = run_import(catalog_code, plan, apply=True)
    print(json.dumps({"catalog": catalog_result}, ensure_ascii=True, indent=2), flush=True)
    history_result = run_import(HISTORY, history, apply=True)
    print(json.dumps({"history": history_result}, ensure_ascii=True, indent=2), flush=True)
    compose("restart", "backend")


if __name__ == "__main__":
    main()
