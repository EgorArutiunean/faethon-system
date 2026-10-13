import hashlib
import os
import subprocess
import time
from pathlib import Path


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
  *" pg_dump "*) printf 'validated-fake-dump\\n' ;;
  *" pg_restore --list "*) exit 0 ;;
  *) exit 0 ;;
esac
""",
        encoding="utf-8",
    )
    executable.chmod(0o755)


def _run_backup(tmp_path: Path, *, fail: bool = False) -> subprocess.CompletedProcess[str]:
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
    recent_dump = backup_dir / "buy_modern_20990101-000000.dump"
    for path in (stale_dump, stale_checksum, unrelated, recent_dump):
        path.write_text("fixture", encoding="utf-8")
    stale_time = time.time() - 20 * 24 * 60 * 60
    for path in (stale_dump, stale_checksum, unrelated):
        os.utime(path, (stale_time, stale_time))

    result = _run_backup(tmp_path)

    assert result.returncode == 0, result.stderr
    assert not stale_dump.exists()
    assert not stale_checksum.exists()
    assert unrelated.exists()
    assert recent_dump.exists()
    generated = sorted(backup_dir.glob("buy_modern_*.dump"))
    assert len(generated) == 2
    assert generated[0].with_suffix(".dump.sha256").exists()
    metrics = (tmp_path / "metrics" / "backup.prom").read_text(encoding="ascii")
    assert "buy_modern_backup_last_attempt_success 1" in metrics
    assert "buy_modern_backup_last_success_timestamp_seconds " in metrics


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


def _run_offsite(tmp_path: Path, *, fail: bool = False) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    _fake_restic(bin_dir)
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(exist_ok=True)
    dump = backup_dir / "buy_modern_20261013-120000.dump"
    dump.write_bytes(b"validated-test-dump")
    digest = hashlib.sha256(dump.read_bytes()).hexdigest()
    dump.with_suffix(".dump.sha256").write_text(
        f"{digest}  {dump.name}\n",
        encoding="ascii",
    )
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
