#!/usr/bin/env sh
set -eu
umask 077

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.production}"
BACKUP_DIR="${BACKUP_DIR:-backups}"
BACKUP_METRICS_FILE="${BACKUP_METRICS_FILE:-}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
BACKUP_COMPOSE_PROJECT="${BACKUP_COMPOSE_PROJECT:-}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

case "$BACKUP_RETENTION_DAYS" in
  ''|*[!0-9]*)
    echo "BACKUP_RETENTION_DAYS must be a non-negative integer" >&2
    exit 1
    ;;
esac

mkdir -p "$BACKUP_DIR"
BACKUP_DIR_ABS="$(cd "$BACKUP_DIR" && pwd -P)"
if [ "$BACKUP_DIR_ABS" = "/" ]; then
  echo "Refusing to use the filesystem root as BACKUP_DIR" >&2
  exit 1
fi

# Kernel lock is released even after a crash; concurrent jobs cannot share a dump.
command -v flock > /dev/null || { echo 'flock is required' >&2; exit 1; }
exec 9> "$BACKUP_DIR_ABS/.backup.lock"
flock -n 9 || { echo 'Another backup is already running' >&2; exit 1; }

BACKUP_FILE="${BACKUP_DIR_ABS}/buy_modern_${TIMESTAMP}.dump"
if [ -e "$BACKUP_FILE" ] || [ -e "$BACKUP_FILE.sha256" ]; then
  echo 'Backup timestamp already exists; refusing to overwrite' >&2
  exit 1
fi
TEMP_FILE="${BACKUP_FILE}.partial"
METRICS_TEMP_FILE=""

write_backup_metrics() {
  attempt_success="$1"
  [ -n "$BACKUP_METRICS_FILE" ] || return 0
  metrics_dir="$(dirname "$BACKUP_METRICS_FILE")"
  mkdir -p -m 0755 "$metrics_dir"
  METRICS_TEMP_FILE="${BACKUP_METRICS_FILE}.partial"
  now="$(date +%s)"
  last_success=""
  if [ "$attempt_success" = "1" ]; then
    last_success="$now"
  elif [ -f "$BACKUP_METRICS_FILE" ]; then
    last_success="$(awk '$1 == "buy_modern_backup_last_success_timestamp_seconds" {print $2; exit}' "$BACKUP_METRICS_FILE")"
  fi
  {
    echo '# HELP buy_modern_backup_last_success_timestamp_seconds Unix timestamp of the latest validated backup.'
    echo '# TYPE buy_modern_backup_last_success_timestamp_seconds gauge'
    if [ -n "$last_success" ]; then
      echo "buy_modern_backup_last_success_timestamp_seconds $last_success"
    fi
    echo '# HELP buy_modern_backup_last_attempt_success Whether the latest backup attempt succeeded.'
    echo '# TYPE buy_modern_backup_last_attempt_success gauge'
    echo "buy_modern_backup_last_attempt_success $attempt_success"
    echo '# HELP buy_modern_backup_last_attempt_timestamp_seconds Unix timestamp of the latest backup attempt.'
    echo '# TYPE buy_modern_backup_last_attempt_timestamp_seconds gauge'
    echo "buy_modern_backup_last_attempt_timestamp_seconds $now"
  } > "$METRICS_TEMP_FILE"
  # Metrics contain no secrets; node_exporter may run as a different user.
  chmod 0644 "$METRICS_TEMP_FILE"
  mv "$METRICS_TEMP_FILE" "$BACKUP_METRICS_FILE"
  METRICS_TEMP_FILE=""
}

cleanup() {
  status="$?"
  rm -f "$TEMP_FILE"
  if [ -n "$METRICS_TEMP_FILE" ]; then
    rm -f "$METRICS_TEMP_FILE"
  fi
  if [ "$status" -ne 0 ]; then
    write_backup_metrics 0 || true
  fi
  exit "$status"
}

trap cleanup EXIT

POSTGRES_CONTAINER=""
if [ -n "$BACKUP_COMPOSE_PROJECT" ]; then
  case "$BACKUP_COMPOSE_PROJECT" in
    *[!A-Za-z0-9_.-]*)
      echo "BACKUP_COMPOSE_PROJECT contains invalid characters" >&2
      exit 1
      ;;
  esac
  POSTGRES_CONTAINER="$(
    docker ps \
      --filter "label=com.docker.compose.project=$BACKUP_COMPOSE_PROJECT" \
      --filter 'label=com.docker.compose.service=postgres' \
      --format '{{.ID}}'
  )"
  if [ -z "$POSTGRES_CONTAINER" ] || [ "$(printf '%s\n' "$POSTGRES_CONTAINER" | wc -l)" -ne 1 ]; then
    echo "Expected exactly one running postgres container for project $BACKUP_COMPOSE_PROJECT" >&2
    exit 1
  fi
elif [ ! -f "$ENV_FILE" ]; then
  echo "Environment file not found: $ENV_FILE" >&2
  exit 1
fi

if [ -n "$POSTGRES_CONTAINER" ]; then
  docker exec -i "$POSTGRES_CONTAINER" \
    sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$TEMP_FILE"
else
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T postgres \
    sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$TEMP_FILE"
fi

if [ ! -s "$TEMP_FILE" ]; then
  echo "Backup is empty: $TEMP_FILE" >&2
  exit 1
fi

if [ -n "$POSTGRES_CONTAINER" ]; then
  docker exec -i "$POSTGRES_CONTAINER" pg_restore --list < "$TEMP_FILE" > /dev/null
else
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T postgres \
    pg_restore --list < "$TEMP_FILE" > /dev/null
fi

mv "$TEMP_FILE" "$BACKUP_FILE"
(
  cd "$BACKUP_DIR_ABS"
  sha256sum "$(basename "$BACKUP_FILE")" > "$(basename "$BACKUP_FILE").sha256"
)

if [ "$BACKUP_RETENTION_DAYS" -gt 0 ]; then
  find "$BACKUP_DIR_ABS" -maxdepth 1 -type f \
    \( -name 'buy_modern_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9].dump' \
    -o -name 'buy_modern_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9].dump.sha256' \) \
    -mtime "+$BACKUP_RETENTION_DAYS" -delete
fi
write_backup_metrics 1
trap - EXIT

echo "Backup written to $BACKUP_FILE"
echo "Checksum written to ${BACKUP_FILE}.sha256"
if [ -n "$BACKUP_METRICS_FILE" ]; then
  echo "Backup freshness metric written to $BACKUP_METRICS_FILE"
fi
echo "Retention applied: $BACKUP_RETENTION_DAYS days"
