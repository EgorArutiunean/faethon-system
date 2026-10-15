#!/usr/bin/env sh
# Restore only into a deliberately selected, empty, isolated database.
set -eu
umask 077

fail() { echo "$*" >&2; exit 1; }
[ "$#" -eq 1 ] || fail 'Usage: scripts/restore_postgres.sh path/to/backup.dump'
BACKUP_FILE="$1"
RESTORE_COMPOSE_PROJECT="${RESTORE_COMPOSE_PROJECT:-}"
RESTORE_EXPECTED_DATABASE="${RESTORE_EXPECTED_DATABASE:-}"
RESTORE_CONFIRM="${RESTORE_CONFIRM:-}"
case "$RESTORE_COMPOSE_PROJECT" in
  ''|*[!a-z0-9_-]*) fail 'RESTORE_COMPOSE_PROJECT must be an explicit safe project name' ;;
esac
case "$RESTORE_EXPECTED_DATABASE" in
  ''|*[!A-Za-z0-9_]*) fail 'RESTORE_EXPECTED_DATABASE must be an explicit safe database name' ;;
esac
[ "$RESTORE_CONFIRM" = "$RESTORE_COMPOSE_PROJECT/$RESTORE_EXPECTED_DATABASE" ] ||
  fail 'RESTORE_CONFIRM must equal project/database; no implicit production target is allowed'
[ -s "$BACKUP_FILE" ] || fail "Backup missing or empty: $BACKUP_FILE"
[ -f "$BACKUP_FILE.sha256" ] || fail 'Checksum sidecar is required'

# Hash the argument itself, never a path supplied by the sidecar. Works from any cwd.
EXPECTED="$(sed 's/\r$//' "$BACKUP_FILE.sha256")"
HASH="${EXPECTED%% *}"
case "$HASH" in ''|*[!0-9a-f]*) fail 'Invalid SHA-256 sidecar' ;; esac
[ "${#HASH}" -eq 64 ] || fail 'Invalid SHA-256 length'
[ "$EXPECTED" = "$HASH  $(basename "$BACKUP_FILE")" ] || fail 'Invalid checksum filename or format'
ACTUAL="$(sha256sum < "$BACKUP_FILE")"
[ "${ACTUAL%% *}" = "$HASH" ] || fail 'Backup checksum mismatch'

POSTGRES_CONTAINER="$(docker ps \
  --filter "label=com.docker.compose.project=$RESTORE_COMPOSE_PROJECT" \
  --filter 'label=com.docker.compose.service=postgres' --format '{{.ID}}')"
[ -n "$POSTGRES_CONTAINER" ] && [ "$(printf '%s\n' "$POSTGRES_CONTAINER" | wc -l)" -eq 1 ] ||
  fail 'Expected exactly one running postgres container for the explicit project'
DATABASE="$(docker exec "$POSTGRES_CONTAINER" printenv POSTGRES_DB)"
[ "$DATABASE" = "$RESTORE_EXPECTED_DATABASE" ] || fail 'Target database does not match RESTORE_EXPECTED_DATABASE'

# Include functions/types and non-public schemas, not just tables.
OBJECT_COUNT="$(docker exec "$POSTGRES_CONTAINER" sh -c '
  exec psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "$1"
' sh "SELECT
  (SELECT count(*) FROM pg_namespace WHERE nspname NOT IN ('public','information_schema') AND nspname !~ '^pg_') +
  (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname != 'information_schema' AND n.nspname !~ '^pg_') +
  (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname != 'information_schema' AND n.nspname !~ '^pg_') +
  (SELECT count(*) FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace WHERE n.nspname != 'information_schema' AND n.nspname !~ '^pg_');")"
[ "$OBJECT_COUNT" = 0 ] || fail 'Target database is not empty; refusing to overwrite existing data'

docker exec -i "$POSTGRES_CONTAINER" pg_restore --list < "$BACKUP_FILE" > /dev/null
docker exec -i "$POSTGRES_CONTAINER" sh -c '
  exec pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    --single-transaction --exit-on-error --no-owner --no-acl
' < "$BACKUP_FILE"
echo "Restore completed into $RESTORE_COMPOSE_PROJECT/$DATABASE"
