import hashlib
import os
import subprocess
import time
from pathlib import Path

import pytest


def _fake_docker(bin_dir: Path) -> None:
    executable = bin_dir / "docker"
    executable.write_text(
        """#!/bin/sh
if [ "${FAKE_DOCKER_FAIL:-0}" = "1" ]; then
  exit 17
fi
case " $* " in
  *" docker ps "*) printf 'fake-container-id\\n' ;;
  *" --format {{.ID}} "*) printf 'fake-container-id\\n' ;;
  *" pg_dump "*) [ "${FAKE_EMPTY_DUMP:-0}" = 1 ] || printf 'validated-fake-dump\\n' ;;
  *" pg_restore --list "*) exit "${FAKE_LIST_EXIT:-0}" ;;
  *) exit 0 ;;
esac
""",
        encoding="utf-8",
    )
    executable.chmod(0o755)


def _run_backup(
    tmp_path: Path, *, fail: bool = False, **overrides: str
) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    _fake_docker(bin_dir)
    backup_dir = tmp_path / "backups"
    metrics_file = tmp_path / "metrics" / "backup.prom"
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "BACKUP_COMPOSE_PROJECT": "buy-modern-production",
            "BACKUP_DIR": str(backup_dir),
            "BACKUP_METRICS_FILE": str(metrics_file),
            "BACKUP_RETENTION_DAYS": "14",
            "FAKE_DOCKER_FAIL": "1" if fail else "0",
        }
    )
    env.update(overrides)
    script = Path(__file__).resolve().parents[2] / "scripts" / "backup_postgres.sh"
    return subprocess.run(
        ["sh", str(script)],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def test_backup_retention_and_success_metrics_are_scoped(tmp_path: Path) -> None:
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    stale_dump = backup_dir / "buy_modern_20200101-000000.dump"
    stale_checksum = backup_dir / "buy_modern_20200101-000000.dump.sha256"
    unrelated = backup_dir / "customer-export.dump"
    similar_name = backup_dir / "buy_modern_manual-export.dump"
    invalid_timestamp = backup_dir / "buy_modern_abcdefgh-ijklmn.dump"
    recent_dump = backup_dir / "buy_modern_20990101-000000.dump"
    for path in (
        stale_dump,
        stale_checksum,
        unrelated,
        recent_dump,
        similar_name,
        invalid_timestamp,
    ):
        path.write_text("fixture", encoding="utf-8")
    stale_time = time.time() - 20 * 24 * 60 * 60
    for path in (stale_dump, stale_checksum, unrelated, similar_name, invalid_timestamp):
        os.utime(path, (stale_time, stale_time))

    result = _run_backup(tmp_path)

    assert result.returncode == 0, result.stderr
    assert not stale_dump.exists()
    assert not stale_checksum.exists()
    assert unrelated.exists()
    assert similar_name.exists()
    assert invalid_timestamp.exists()
    assert recent_dump.exists()
    generated = sorted(backup_dir.glob("buy_modern_*.dump"))
    generated = [path for path in generated if path not in (similar_name, invalid_timestamp)]
    assert len(generated) == 2
    assert generated[0].with_suffix(".dump.sha256").exists()
    metrics = (tmp_path / "metrics" / "backup.prom").read_text(encoding="ascii")
    assert "buy_modern_backup_last_attempt_success 1" in metrics
    assert "buy_modern_backup_last_success_timestamp_seconds " in metrics


def test_concurrent_backup_does_not_touch_existing_files(tmp_path: Path) -> None:
    import fcntl

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    with (backup_dir / ".backup.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = _run_backup(tmp_path)
    assert result.returncode != 0
    assert "already running" in result.stderr
    assert not list(backup_dir.glob("*.dump*"))


def test_backup_permissions_and_readable_metrics(tmp_path: Path) -> None:
    result = _run_backup(tmp_path)
    assert result.returncode == 0, result.stderr
    dump = next((tmp_path / "backups").glob("*.dump"))
    assert dump.stat().st_mode & 0o777 == 0o600
    assert dump.with_suffix(".dump.sha256").stat().st_mode & 0o777 == 0o600
    assert (tmp_path / "metrics" / "backup.prom").stat().st_mode & 0o777 == 0o644


@pytest.mark.parametrize("overrides", [{"FAKE_EMPTY_DUMP": "1"}, {"FAKE_LIST_EXIT": "1"}])
def test_invalid_dump_is_not_published(tmp_path: Path, overrides: dict[str, str]) -> None:
    result = _run_backup(tmp_path, **overrides)
    assert result.returncode != 0
    assert not list((tmp_path / "backups").glob("*.dump*"))
    assert not list((tmp_path / "backups").glob("*.partial"))
    assert (
        "buy_modern_backup_last_attempt_success 0"
        in (tmp_path / "metrics" / "backup.prom").read_text()
    )


def test_retention_can_be_disabled(tmp_path: Path) -> None:
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    stale = backup_dir / "buy_modern_20200101-000000.dump"
    stale.write_bytes(b"keep me")
    os.utime(stale, (1, 1))
    result = _run_backup(tmp_path, BACKUP_RETENTION_DAYS="0")
    assert result.returncode == 0, result.stderr
    assert stale.read_bytes() == b"keep me"


def test_existing_timestamp_cannot_be_overwritten(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    date = bin_dir / "date"
    date.write_text(
        '#!/bin/sh\nif [ "$1" = \'+%Y%m%d-%H%M%S\' ]; then echo 20261015-120000; else /bin/date "$@"; fi\n'
    )
    date.chmod(0o755)
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    existing = backup_dir / "buy_modern_20261015-120000.dump"
    existing.write_bytes(b"previous backup")
    result = _run_backup(tmp_path)
    assert result.returncode != 0
    assert "refusing to overwrite" in result.stderr
    assert existing.read_bytes() == b"previous backup"


def _run_restore(tmp_path: Path, **overrides: str) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    docker = bin_dir / "docker"
    docker.write_text(
        """#!/bin/sh
printf '%s\\n' "$*" >> "$DOCKER_LOG"
case " $* " in
  *" ps "*) printf '%s\\n' "${FAKE_CONTAINERS-container-id}" ;;
  *" printenv POSTGRES_DB "*) printf '%s\\n' "${FAKE_DATABASE-drill_db}" ;;
  *" psql "*) printf '%s\\n' "${FAKE_OBJECTS-0}" ;;
  *" pg_restore --list "*) cat >/dev/null; exit "${FAKE_LIST_EXIT-0}" ;;
  *" pg_restore "*) cat >/dev/null; exit "${FAKE_RESTORE_EXIT-0}" ;;
  *) exit 2 ;;
esac
""",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    dump = tmp_path / "nested path" / "fixture.dump"
    dump.parent.mkdir(exist_ok=True)
    dump.write_bytes(b"synthetic-dump")
    digest = hashlib.sha256(dump.read_bytes()).hexdigest()
    checksum = dump.with_suffix(".dump.sha256")
    checksum.write_text(f"{digest}  {dump.name}\n", encoding="ascii")
    if overrides.pop("CRLF_CHECKSUM", ""):
        checksum.write_bytes(f"{digest}  {dump.name}\r\n".encode("ascii"))
    if overrides.pop("MISSING_CHECKSUM", ""):
        checksum.unlink()
    if overrides.pop("CORRUPT_DUMP", ""):
        dump.write_bytes(b"corrupted")
    if overrides.pop("WRONG_FILENAME", ""):
        checksum.write_text(f"{digest}  another.dump\n", encoding="ascii")
    env = os.environ.copy()
    env.update(
        PATH=f"{bin_dir}:{env['PATH']}",
        DOCKER_LOG=str(tmp_path / "docker.log"),
        RESTORE_COMPOSE_PROJECT="isolated-drill",
        RESTORE_EXPECTED_DATABASE="drill_db",
        RESTORE_CONFIRM="isolated-drill/drill_db",
    )
    env.update(overrides)
    script = Path(__file__).resolve().parents[2] / "scripts" / "restore_postgres.sh"
    return subprocess.run(
        ["sh", str(script), str(dump)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_restore_from_other_directory_is_transactional(tmp_path: Path) -> None:
    result = _run_restore(tmp_path)
    assert result.returncode == 0, result.stderr
    log = (tmp_path / "docker.log").read_text()
    assert "label=com.docker.compose.project=isolated-drill" in log
    assert "--single-transaction --exit-on-error --no-owner --no-acl" in log
    assert "--clean" not in log


def test_restore_accepts_windows_checksum_line_endings(tmp_path: Path) -> None:
    result = _run_restore(tmp_path, CRLF_CHECKSUM="1")
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "overrides",
    [
        {"RESTORE_CONFIRM": ""},
        {"RESTORE_COMPOSE_PROJECT": ""},
        {"RESTORE_EXPECTED_DATABASE": ""},
        {"MISSING_CHECKSUM": "1"},
        {"CORRUPT_DUMP": "1"},
        {"WRONG_FILENAME": "1"},
    ],
)
def test_restore_invalid_input_never_calls_docker(
    tmp_path: Path, overrides: dict[str, str]
) -> None:
    result = _run_restore(tmp_path, **overrides)
    assert result.returncode != 0
    assert not (tmp_path / "docker.log").exists()


@pytest.mark.parametrize(
    "overrides",
    [
        {"FAKE_CONTAINERS": ""},
        {"FAKE_CONTAINERS": "one\ntwo"},
        {"FAKE_DATABASE": "production"},
        {"FAKE_OBJECTS": "1"},
        {"FAKE_OBJECTS": "unexpected"},
        {"FAKE_LIST_EXIT": "1"},
    ],
)
def test_restore_invalid_target_never_writes(tmp_path: Path, overrides: dict[str, str]) -> None:
    result = _run_restore(tmp_path, **overrides)
    assert result.returncode != 0
    assert "--single-transaction" not in (tmp_path / "docker.log").read_text()


def test_restore_failure_is_not_reported_as_success(tmp_path: Path) -> None:
    result = _run_restore(tmp_path, FAKE_RESTORE_EXIT="17")
    assert result.returncode != 0
    assert "Restore completed" not in result.stdout


def test_failed_backup_metric_preserves_previous_success(tmp_path: Path) -> None:
    metrics_file = tmp_path / "metrics" / "backup.prom"
    metrics_file.parent.mkdir()
    metrics_file.write_text(
        "buy_modern_backup_last_success_timestamp_seconds 1234567890\n",
        encoding="ascii",
    )

    result = _run_backup(tmp_path, fail=True)

    assert result.returncode != 0
    metrics = metrics_file.read_text(encoding="ascii")
    assert "buy_modern_backup_last_attempt_success 0" in metrics
    assert "buy_modern_backup_last_success_timestamp_seconds 1234567890" in metrics


def _fake_restic(bin_dir: Path) -> None:
    executable = bin_dir / "restic"
    executable.write_text(
        """#!/bin/sh
printf '%s\\n' "$*" >> "$FAKE_RESTIC_LOG"
if [ "${FAKE_RESTIC_FAIL:-0}" = "1" ]; then
  exit 19
fi
case "$1" in
  backup|snapshots) exit 0 ;;
  *) exit 2 ;;
esac
""",
        encoding="utf-8",
    )
    executable.chmod(0o755)


def _run_offsite(
    tmp_path: Path, *, fail: bool = False, wrong_checksum: bool = False, crlf_checksum: bool = False
) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    _fake_restic(bin_dir)
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(exist_ok=True)
    dump = backup_dir / "buy_modern_20261013-120000.dump"
    dump.write_bytes(b"validated-test-dump")
    digest = hashlib.sha256(dump.read_bytes()).hexdigest()
    dump.with_suffix(".dump.sha256").write_text(
        f"{digest}  {'another.dump' if wrong_checksum else dump.name}\n",
        encoding="ascii",
    )
    if crlf_checksum:
        dump.with_suffix(".dump.sha256").write_bytes(f"{digest}  {dump.name}\r\n".encode("ascii"))
    password_file = tmp_path / "restic-password"
    password_file.write_text("test-only-password\n", encoding="ascii")
    password_file.chmod(0o600)
    metrics_file = tmp_path / "metrics" / "offsite.prom"
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "OFFSITE_BACKUP_ENABLED": "true",
            "BACKUP_DIR": str(backup_dir),
            "OFFSITE_METRICS_FILE": str(metrics_file),
            "RESTIC_REPOSITORY": "s3:https://storage.example.test/bucket",
            "RESTIC_PASSWORD_FILE": str(password_file),
            "RESTIC_BACKUP_HOST": "test-host",
            "FAKE_RESTIC_LOG": str(tmp_path / "restic.log"),
            "FAKE_RESTIC_FAIL": "1" if fail else "0",
        }
    )
    script = Path(__file__).resolve().parents[2] / "scripts" / "offsite_backup.sh"
    return subprocess.run(
        ["sh", str(script)],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def test_offsite_backup_uploads_validated_pair_and_writes_success_metric(
    tmp_path: Path,
) -> None:
    result = _run_offsite(tmp_path)

    assert result.returncode == 0, result.stderr
    log = (tmp_path / "restic.log").read_text(encoding="utf-8")
    assert "backup --host test-host --tag buy-modern-postgres" in log
    assert "buy_modern_20261013-120000.dump.sha256" in log
    assert "snapshots --host test-host --tag buy-modern-postgres --latest 1 --json" in log
    metrics = (tmp_path / "metrics" / "offsite.prom").read_text(encoding="ascii")
    assert "buy_modern_offsite_backup_last_attempt_success 1" in metrics
    assert "buy_modern_offsite_backup_last_success_timestamp_seconds " in metrics
    assert (tmp_path / "metrics" / "offsite.prom").stat().st_mode & 0o777 == 0o644


def test_offsite_rejects_checksum_for_another_file(tmp_path: Path) -> None:
    result = _run_offsite(tmp_path, wrong_checksum=True)
    assert result.returncode != 0
    assert "checksum mismatch" in result.stderr
    assert not (tmp_path / "restic.log").exists()


def test_offsite_accepts_windows_checksum_line_endings(tmp_path: Path) -> None:
    result = _run_offsite(tmp_path, crlf_checksum=True)
    assert result.returncode == 0, result.stderr


def test_failed_offsite_backup_preserves_previous_success(tmp_path: Path) -> None:
    metrics_file = tmp_path / "metrics" / "offsite.prom"
    metrics_file.parent.mkdir()
    metrics_file.write_text(
        "buy_modern_offsite_backup_last_success_timestamp_seconds 1234567890\n",
        encoding="ascii",
    )

    result = _run_offsite(tmp_path, fail=True)

    assert result.returncode != 0
    metrics = metrics_file.read_text(encoding="ascii")
    assert "buy_modern_offsite_backup_last_attempt_success 0" in metrics
    assert "buy_modern_offsite_backup_last_success_timestamp_seconds 1234567890" in metrics
