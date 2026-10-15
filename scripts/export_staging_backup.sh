#!/usr/bin/env sh
# Read-only SSH forced command: list completed staging dumps or get one exact file.
set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin
LC_ALL=C
export PATH LC_ALL
SOURCE_DIR='/var/backups/buy-staging'
readonly SOURCE_DIR

fail() { printf '%s\n' "$1" >&2; exit 1; }
[ "$#" -eq 0 ] || fail 'Arguments to the forced-command script are not allowed'

case "${SSH_ORIGINAL_COMMAND:-}" in
  list) OPERATION=list; REQUEST='' ;;
  'get '*) OPERATION=get; REQUEST="${SSH_ORIGINAL_COMMAND#get }" ;;
  *) fail 'Only list or get BASENAME is allowed' ;;
esac

[ -d "$SOURCE_DIR" ] && [ ! -L "$SOURCE_DIR" ] || fail 'Backup source is not a real directory'
[ "$(readlink -f -- "$SOURCE_DIR")" = "$SOURCE_DIR" ] || fail 'Backup source must not contain symlinks'

serve_pair() (
  requested="$1"
  operation="$2"
  dump_name="${requested%.sha256}"
  case "$dump_name" in
    buy_modern_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9].dump) ;;
    *) exit 1 ;;
  esac
  case "$requested" in
    "$dump_name"|"$dump_name.sha256") ;;
    *) exit 1 ;;
  esac

  dump_path="$SOURCE_DIR/$dump_name"
  checksum_path="$dump_path.sha256"
  [ -f "$dump_path" ] && [ ! -L "$dump_path" ] && [ -s "$dump_path" ] || exit 1
  [ -f "$checksum_path" ] && [ ! -L "$checksum_path" ] || exit 1
  exec 3< "$dump_path" || exit 1
  exec 4< "$checksum_path" || exit 1
  # Retention may remove a pathname concurrently. Verify descriptors and read the
  # same opened files throughout; never follow a sidecar-supplied filename.
  [ -f /proc/self/fd/3 ] && [ -f /proc/self/fd/4 ] || exit 1
  [ "$(readlink -f /proc/self/fd/3)" = "$dump_path" ] || exit 1
  [ "$(readlink -f /proc/self/fd/4)" = "$checksum_path" ] || exit 1

  actual="$(sha256sum /proc/self/fd/3)" || exit 1
  actual="${actual%% *}"
  expected="$actual  $dump_name"
  expected_size="${#expected}"
  checksum_size="$(stat -Lc '%s' /proc/self/fd/4)" || exit 1
  case "$checksum_size" in
    "$expected_size") printf '%s' "$expected" | cmp -s - /proc/self/fd/4 || exit 1 ;;
    "$((expected_size + 1))") printf '%s\n' "$expected" | cmp -s - /proc/self/fd/4 || exit 1 ;;
    "$((expected_size + 2))") printf '%s\r\n' "$expected" | cmp -s - /proc/self/fd/4 || exit 1 ;;
    *) exit 1 ;;
  esac

  if [ "$operation" = list ]; then
    printf '%s\n' "$dump_name"
  elif [ "$requested" = "$dump_name" ]; then
    cat /proc/self/fd/3
  else
    cat /proc/self/fd/4
  fi
)

if [ "$OPERATION" = list ]; then
  for dump_path in "$SOURCE_DIR"/buy_modern_*.dump; do
    if serve_pair "${dump_path##*/}" list; then :; fi
  done
else
  serve_pair "$REQUEST" get || fail 'Requested backup pair is unavailable or invalid'
fi
