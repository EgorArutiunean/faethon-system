#!/usr/bin/env python3
"""Real PostgreSQL backup/restore rehearsal using synthetic data only.

Creates two NEW network-isolated containers with tmpfs PGDATA, no published ports
and unique labels. Never discovers existing application containers. Removes only
the containers created by this invocation. Requires a locally available PG image,
Docker, and sh (Linux) or PowerShell 7 (Windows). --shell additionally exercises
the POSIX restore script on Windows using Git Bash.
"""

import argparse
import hashlib
import os
import secrets
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POSTGRES_IMAGE = (
    "postgres:16@sha256:71e27bf60b70bded003791b5573f8b808365613f341df20ffcf0c1ed7bc13ddf"
)


def run(command: list[str], **kwargs) -> str:
    result = subprocess.run(command, capture_output=True, text=True, check=False, **kwargs)
    if result.returncode:
        # Do not print commands: docker run arguments include a random test password.
        raise RuntimeError(f"Command failed ({result.returncode}): {result.stderr[-4000:]}")
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--postgres-image", default=POSTGRES_IMAGE)
    parser.add_argument("--shell", help="Optional POSIX shell to test restore on Windows")
    parser.add_argument("--powershell", default="pwsh")
    args = parser.parse_args()
    # Fail before creating containers if a required local image or runtime is absent.
    run(["docker", "image", "inspect", args.postgres_image])
    windows = os.name == "nt"
    runtime = args.powershell if windows else "sh"
    if not shutil.which(runtime):
        raise RuntimeError(f"Runtime not available: {runtime}")
    if args.shell and not Path(args.shell).is_file():
        raise RuntimeError("--shell must name an existing executable")
    token = uuid.uuid4().hex[:12]
    source_project = f"buy-backup-drill-{token}-source"
    target_project = f"buy-backup-drill-{token}-target"
    created: list[str] = []
    started = time.monotonic()

    def sql(container: str, query: str) -> str:
        return run(
            [
                "docker",
                "exec",
                container,
                "psql",
                "-X",
                "-v",
                "ON_ERROR_STOP=1",
                "-U",
                "drill",
                "-d",
                "drill_db",
                "-Atc",
                query,
            ]
        )

    def create(project: str) -> str:
        container = run(
            [
                "docker",
                "run",
                "-d",
                "--pull",
                "never",
                "--network",
                "none",
                "--memory",
                "384m",
                "--cpus",
                "1",
                "--pids-limit",
                "100",
                "--label",
                f"buy-modern.restore-drill={token}",
                "--label",
                f"com.docker.compose.project={project}",
                "--label",
                "com.docker.compose.service=postgres",
                "--tmpfs",
                "/var/lib/postgresql/data:rw,nosuid,size=256m",
                "-e",
                "POSTGRES_USER=drill",
                "-e",
                "POSTGRES_DB=drill_db",
                "-e",
                f"POSTGRES_PASSWORD={secrets.token_hex(24)}",
                args.postgres_image,
            ]
        )
        created.append(container)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                sql(container, "SELECT 1")
                # initdb starts a temporary socket-only server; wait for the final server.
                run(
                    [
                        "docker",
                        "exec",
                        container,
                        "pg_isready",
                        "-h",
                        "127.0.0.1",
                        "-U",
                        "drill",
                        "-d",
                        "drill_db",
                    ]
                )
                return container
            except RuntimeError:
                time.sleep(0.5)
        raise RuntimeError("Disposable PostgreSQL did not become ready in 60 seconds")

    try:
        source = create(source_project)
        target = create(target_project)
        sql(
            source,
            "CREATE TABLE inventory (id integer PRIMARY KEY, name text NOT NULL, amount numeric(12,2));"
            "INSERT INTO inventory VALUES (1,'Тестовый товар',12.34),(2,'Fixture',100.00),(3,'Sample',23.95);",
        )
        with tempfile.TemporaryDirectory(prefix="buy-backup-drill-") as directory:
            work = Path(directory)
            backups = work / "backups with spaces"
            env = os.environ.copy()
            # Clear inherited operator settings so this drill cannot use their targets/metrics.
            for key in list(env):
                if key.upper().startswith(("BACKUP_", "RESTORE_", "COMPOSE_")):
                    env.pop(key)
            env["MSYS_NO_PATHCONV"] = "1"
            if windows:
                run(
                    [
                        runtime,
                        "-NoProfile",
                        "-NonInteractive",
                        "-File",
                        str(ROOT / "scripts/backup_postgres.ps1"),
                        "-ComposeProject",
                        source_project,
                        "-BackupDir",
                        str(backups),
                        "-RetentionDays",
                        "0",
                    ],
                    env=env,
                )
            else:
                env.update(
                    BACKUP_COMPOSE_PROJECT=source_project,
                    BACKUP_DIR=str(backups),
                    BACKUP_RETENTION_DAYS="0",
                )
                run(["sh", str(ROOT / "scripts/backup_postgres.sh")], env=env)
            dumps = list(backups.glob("*.dump"))
            if len(dumps) != 1:
                raise RuntimeError("Expected exactly one generated backup")
            dump = dumps[0]
            checksum = dump.with_suffix(".dump.sha256")
            expected = hashlib.sha256(dump.read_bytes()).hexdigest()
            if checksum.read_text().strip() != f"{expected}  {dump.name}":
                raise RuntimeError("Backup checksum mismatch")
            print("PASS: real custom-format backup and SHA-256", flush=True)

            variants = ["powershell"] if windows else ["sh"]
            if windows and args.shell:
                variants.append("sh")

            def restore(
                variant: str,
                backup: Path,
                *,
                confirm: str | None = None,
                database: str = "drill_db",
                failure: str | None = None,
            ) -> None:
                confirmation = confirm if confirm is not None else f"{target_project}/{database}"
                child_env = env.copy()
                if variant == "powershell":
                    command = [
                        runtime,
                        "-NoProfile",
                        "-NonInteractive",
                        "-File",
                        str(ROOT / "scripts/restore_postgres.ps1"),
                        "-BackupFile",
                        str(backup),
                        "-ComposeProject",
                        target_project,
                        "-ExpectedDatabase",
                        database,
                        "-ConfirmRestore",
                        confirmation,
                    ]
                else:
                    child_env.update(
                        RESTORE_COMPOSE_PROJECT=target_project,
                        RESTORE_EXPECTED_DATABASE=database,
                        RESTORE_CONFIRM=confirmation,
                    )
                    command = [
                        args.shell or "sh",
                        (ROOT / "scripts/restore_postgres.sh").as_posix(),
                        backup.as_posix(),
                    ]
                result = subprocess.run(
                    command,
                    cwd=work,
                    env=child_env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if failure:
                    if result.returncode == 0 or failure not in result.stdout + result.stderr:
                        raise RuntimeError(
                            f"Expected refusal containing {failure}: {result.stderr}"
                        )
                elif result.returncode:
                    raise RuntimeError(f"Restore failed: {result.stderr}")

            for variant in variants:
                restore(variant, dump, confirm="wrong-target", failure="must equal")
                restore(variant, dump, database="wrong_db", failure="does not match")
                invalid = backups / f"invalid-{variant}.dump"
                invalid.write_bytes(b"corrupt")
                restore(variant, invalid, failure="Checksum sidecar is required")
                invalid.with_suffix(".dump.sha256").write_text(f"{expected}  {invalid.name}\n")
                restore(variant, invalid, failure="checksum mismatch")
                restore(variant, dump)
                observed = sql(target, "SELECT count(*) || ':' || sum(amount) FROM inventory")
                if observed != "3:136.29":
                    raise RuntimeError(f"Restored values differ: {observed}")
                # UTF-8 is checked server-side to avoid Windows console codepage effects.
                if sql(target, "SELECT length(name) FROM inventory WHERE id=1") != "14":
                    raise RuntimeError("UTF-8 fixture did not roundtrip")
                restore(variant, dump, failure="not empty")
                if sql(target, "SELECT count(*) || ':' || sum(amount) FROM inventory") != observed:
                    raise RuntimeError("Refused restore modified existing data")
                print(
                    f"PASS: {variant} restore, guards, reconciliation and non-empty refusal",
                    flush=True,
                )
                sql(target, "DROP SCHEMA public CASCADE; CREATE SCHEMA public;")

            # Deliberately broken archive: table default depends on an excluded function.
            # a_marker is restored first, then z_broken fails; transaction must undo both.
            sql(
                source,
                "CREATE TABLE a_marker (id integer);"
                "CREATE FUNCTION needed_function() RETURNS integer LANGUAGE sql AS 'SELECT 1';"
                "CREATE TABLE z_broken (id integer DEFAULT needed_function());",
            )
            broken = backups / "transaction-failure.dump"
            with broken.open("wb") as output:
                subprocess.run(
                    [
                        "docker",
                        "exec",
                        source,
                        "pg_dump",
                        "-U",
                        "drill",
                        "-d",
                        "drill_db",
                        "-Fc",
                        "-t",
                        "a_marker",
                        "-t",
                        "z_broken",
                    ],
                    stdout=output,
                    check=True,
                )
            broken.with_suffix(".dump.sha256").write_text(
                f"{hashlib.sha256(broken.read_bytes()).hexdigest()}  {broken.name}\n"
            )
            for variant in variants:
                restore(variant, broken, failure="needed_function")
                if (
                    sql(
                        target,
                        "SELECT count(*) FROM pg_class WHERE relnamespace='public'::regnamespace",
                    )
                    != "0"
                ):
                    raise RuntimeError("Failed restore left partial tables")
                print(f"PASS: {variant} failed restore rolled back all tables", flush=True)
        print(
            f"PASS: synthetic drill completed in {time.monotonic() - started:.1f}s",
            flush=True,
        )
    finally:
        for container in reversed(created):
            owner = run(
                [
                    "docker",
                    "inspect",
                    "-f",
                    '{{index .Config.Labels "buy-modern.restore-drill"}}',
                    container,
                ]
            )
            if owner != token:
                raise RuntimeError("Refusing cleanup: test ownership label does not match")
            run(["docker", "rm", "-f", "-v", container])
        print(
            "Cleanup: removed only this drill's disposable containers/PGDATA",
            flush=True,
        )


if __name__ == "__main__":
    main()
