#!/usr/bin/env sh
set -eu

OFFSITE_BACKUP_ENABLED="${OFFSITE_BACKUP_ENABLED:-false}"
BACKUP_DIR="${BACKUP_DIR:-backups}"
OFFSITE_METRICS_FILE="${OFFSITE_METRICS_FILE:-}"
RESTIC_BACKUP_TAG="${RESTIC_BACKUP_TAG:-buy-modern-postgres}"
RESTIC_BACKUP_HOST="${RESTIC_BACKUP_HOST:-$(hostname -f 2>/dev/null || hostname)}"
METRICS_TEMP_FILE=""

write_offsite_metrics() {
  attempt_success="$1"
  [ -n "$OFFSITE_METRICS_FILE" ] || return 0
  metrics_dir="$(dirname "$OFFSITE_METRICS_FILE")"
  mkdir -p "$metrics_dir"
  METRICS_TEMP_FILE="${OFFSITE_METRICS_FILE}.partial"
  now="$(date +%s)"
  last_success=""
  if [ "$attempt_success" = "1" ]; then
    last_success="$now"
  elif [ -f "$OFFSITE_METRICS_FILE" ]; then
    last_success="$(awk '$1 == "buy_modern_offsite_backup_last_success_timestamp_seconds" {print $2; exit}' "$OFFSITE_METRICS_FILE")"
  fi
  {
    echo '# HELP buy_modern_offsite_backup_last_success_timestamp_seconds Unix timestamp of the latest encrypted offsite backup.'
    echo '# TYPE buy_modern_offsite_backup_last_success_timestamp_seconds gauge'
    if [ -n "$last_success" ]; then
      echo "buy_modern_offsite_backup_last_success_timestamp_seconds $last_success"
    fi
    echo '# HELP buy_modern_offsite_backup_last_attempt_success Whether the latest encrypted offsite backup attempt succeeded.'
    echo '# TYPE buy_modern_offsite_backup_last_attempt_success gauge'
    echo "buy_modern_offsite_backup_last_attempt_success $attempt_success"
    echo '# HELP buy_modern_offsite_backup_last_attempt_timestamp_seconds Unix timestamp of the latest encrypted offsite backup attempt.'
    echo '# TYPE buy_modern_offsite_backup_last_attempt_timestamp_seconds gauge'
    echo "buy_modern_offsite_backup_last_attempt_timestamp_seconds $now"
  } > "$METRICS_TEMP_FILE"
  mv "$METRICS_TEMP_FILE" "$OFFSITE_METRICS_FILE"
  METRICS_TEMP_FILE=""
}

cleanup() {
  status="$?"
  if [ -n "$METRICS_TEMP_FILE" ]; then
    rm -f "$METRICS_TEMP_FILE"
  fi
  if [ "$status" -ne 0 ]; then
    write_offsite_metrics 0 || true
  fi
  exit "$status"
}

case "$OFFSITE_BACKUP_ENABLED" in
  true) ;;
  false)
    echo "Encrypted offsite backup is disabled"
    exit 0
    ;;
  *)
    echo "OFFSITE_BACKUP_ENABLED must be true or false" >&2
    exit 1
    ;;
esac

trap cleanup EXIT

: "${RESTIC_REPOSITORY:?RESTIC_REPOSITORY is required}"
: "${RESTIC_PASSWORD_FILE:?RESTIC_PASSWORD_FILE is required}"

command -v restic > /dev/null 2>&1 || {
  echo "restic is not installed" >&2
  exit 1
}

if [ ! -f "$RESTIC_PASSWORD_FILE" ]; then
  echo "RESTIC_PASSWORD_FILE does not exist: $RESTIC_PASSWORD_FILE" >&2
  exit 1
fi

password_mode="$(stat -c '%a' "$RESTIC_PASSWORD_FILE")"
if [ $((password_mode % 100)) -ne 0 ]; then
  echo "RESTIC_PASSWORD_FILE must not be readable or writable by group/others" >&2
  exit 1
fi

if [ ! -d "$BACKUP_DIR" ]; then
  echo "BACKUP_DIR does not exist: $BACKUP_DIR" >&2
  exit 1
fi
BACKUP_DIR_ABS="$(cd "$BACKUP_DIR" && pwd -P)"

latest_dump="$(
  find "$BACKUP_DIR_ABS" -maxdepth 1 -type f -name 'buy_modern_????????-??????.dump' -print \
    | sort \
    | tail -n 1
)"
if [ -z "$latest_dump" ]; then
  echo "No validated PostgreSQL dump found in $BACKUP_DIR_ABS" >&2
  exit 1
fi

checksum_file="${latest_dump}.sha256"
if [ ! -f "$checksum_file" ]; then
  echo "Checksum file is missing: $checksum_file" >&2
  exit 1
fi
(
  cd "$BACKUP_DIR_ABS"
  sha256sum -c "$(basename "$checksum_file")" > /dev/null
)

export RESTIC_REPOSITORY RESTIC_PASSWORD_FILE
restic backup \
  --host "$RESTIC_BACKUP_HOST" \
  --tag "$RESTIC_BACKUP_TAG" \
  "$latest_dump" "$checksum_file"
restic snapshots \
  --host "$RESTIC_BACKUP_HOST" \
  --tag "$RESTIC_BACKUP_TAG" \
  --latest 1 \
  --json > /dev/null

write_offsite_metrics 1
trap - EXIT

echo "Encrypted offsite backup completed for $(basename "$latest_dump")"
if [ -n "$OFFSITE_METRICS_FILE" ]; then
  echo "Offsite backup metric written to $OFFSITE_METRICS_FILE"
fi
