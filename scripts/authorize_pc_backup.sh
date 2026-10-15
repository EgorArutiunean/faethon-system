#!/usr/bin/env sh
# Run manually in the staging host terminal to install one read-only SSH key.
set -eu
umask 077
PATH=/usr/sbin:/usr/bin:/sbin:/bin
LC_ALL=C
export PATH LC_ALL

fail() { printf '%s\n' "$1" >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || fail 'Run as root in the staging host terminal'
[ "$#" -eq 0 ] || fail 'Use PC_BACKUP_TOOLING_REF and PC_BACKUP_PUBLIC_KEY, not arguments'
for required in curl sha256sum ssh-keygen sh readlink stat install mktemp awk grep tail od tr; do
  command -v "$required" > /dev/null || fail "Required command is missing: $required"
done

: "${PC_BACKUP_TOOLING_REF:?Set PC_BACKUP_TOOLING_REF to the full pinned tooling commit SHA}"
: "${PC_BACKUP_PUBLIC_KEY:?Set PC_BACKUP_PUBLIC_KEY to the dedicated ssh-ed25519 public key}"
case "$PC_BACKUP_TOOLING_REF" in *[!0-9a-f]*) fail 'Tooling ref must contain lowercase hex only' ;; esac
[ "${#PC_BACKUP_TOOLING_REF}" -eq 40 ] || fail 'Tooling ref must be a full 40-character commit SHA'

newline='
'
carriage_return="$(printf '\r')"
case "$PC_BACKUP_PUBLIC_KEY" in
  *"$newline"*|*"$carriage_return"*) fail 'Public key must be a single line without CR or LF' ;;
  'ssh-ed25519 '*) ;;
  *) fail 'Only a dedicated ssh-ed25519 public key is accepted' ;;
esac
key_fields="${PC_BACKUP_PUBLIC_KEY#ssh-ed25519 }"
key_blob="${key_fields%% *}"
case "$key_blob" in ''|*[!A-Za-z0-9+/=]*) fail 'Public key has an invalid base64 field' ;; esac
[ "${#key_blob}" -eq 68 ] || fail 'Public key is not a canonical Ed25519 public key'

EXPORTER_PATH=/opt/buy-modern/current/scripts/export_staging_backup.sh
EXPORTER_SHA=0c5d3a37b1b9293e50ee1ab940333d5c41889a3b56f662d091cb894447248e4c
SSH_DIR=/root/.ssh
AUTHORIZED_KEYS="$SSH_DIR/authorized_keys"
FORCED_LINE="restrict,command=\"/bin/sh $EXPORTER_PATH\" $PC_BACKUP_PUBLIC_KEY"
readonly EXPORTER_PATH EXPORTER_SHA SSH_DIR AUTHORIZED_KEYS FORCED_LINE

[ "$(readlink -m -- "$SSH_DIR")" = "$SSH_DIR" ] || fail 'SSH directory path must not contain symlinks'
if [ -e "$SSH_DIR" ]; then
  [ -d "$SSH_DIR" ] && [ ! -L "$SSH_DIR" ] || fail 'SSH directory has an unexpected type'
  [ "$(stat -c '%u' "$SSH_DIR")" -eq 0 ] || fail 'Existing SSH directory must be owned by root'
fi
[ ! -L "$AUTHORIZED_KEYS" ] || fail 'Refusing a symlinked authorized_keys file'
if [ -e "$AUTHORIZED_KEYS" ]; then
  [ -f "$AUTHORIZED_KEYS" ] || fail 'authorized_keys must be a regular file'
  [ "$(stat -c '%u' "$AUTHORIZED_KEYS")" -eq 0 ] || fail 'Existing authorized_keys must be owned by root'
  [ "$(stat -c '%h' "$AUTHORIZED_KEYS")" -eq 1 ] || fail 'Refusing a hard-linked authorized_keys file'
fi
[ "$(readlink -m -- "$EXPORTER_PATH")" = "$EXPORTER_PATH" ] || fail 'Exporter path must not contain symlinks'
if [ -e "$EXPORTER_PATH" ]; then
  [ -f "$EXPORTER_PATH" ] && [ ! -L "$EXPORTER_PATH" ] || fail 'Existing exporter must be a regular file'
  installed_sha="$(sha256sum "$EXPORTER_PATH")"
  [ "${installed_sha%% *}" = "$EXPORTER_SHA" ] || fail 'Existing exporter differs from the approved version'
fi

already_authorized=0
if [ -f "$AUTHORIZED_KEYS" ]; then
  key_matches="$(awk -v blob="$key_blob" '
    /^[[:space:]]*#/ { next }
    { for (i = 1; i <= NF; i++) if ($i == blob) { count++; break } }
    END { print count + 0 }
  ' "$AUTHORIZED_KEYS")"
  if [ "$key_matches" -gt 0 ]; then
    [ "$key_matches" -eq 1 ] && grep -Fqx -- "$FORCED_LINE" "$AUTHORIZED_KEYS" ||
      fail 'This public key already exists with a different line or duplicate authorization; use a separate key'
    already_authorized=1
  fi
fi

PC_KEY_WORKDIR="$(mktemp -d /root/buy-modern-pc-backup-key.XXXXXX)"
printf '%s\n' "$PC_BACKUP_PUBLIC_KEY" > "$PC_KEY_WORKDIR/public-key.pub"
ssh-keygen -lf "$PC_KEY_WORKDIR/public-key.pub" > /dev/null || fail 'ssh-keygen rejected the public key'
curl --fail --show-error --silent --location \
  "https://raw.githubusercontent.com/EgorArutiunean/faethon-system/$PC_BACKUP_TOOLING_REF/scripts/export_staging_backup.sh" \
  --output "$PC_KEY_WORKDIR/export_staging_backup.sh"
printf '%s  %s\n' "$EXPORTER_SHA" "$PC_KEY_WORKDIR/export_staging_backup.sh" | sha256sum -c -
sh -n "$PC_KEY_WORKDIR/export_staging_backup.sh"

if [ -f "$AUTHORIZED_KEYS" ]; then
  install -o root -g root -m 0600 "$AUTHORIZED_KEYS" "$PC_KEY_WORKDIR/authorized_keys.before"
else
  printf '%s\n' 'authorized_keys did not exist before this installation' > "$PC_KEY_WORKDIR/authorized_keys.was-absent"
fi
printf 'Previous authorization saved in: %s\n' "$PC_KEY_WORKDIR"

install -d -o root -g root -m 0755 /opt/buy-modern/current/scripts
install -o root -g root -m 0644 "$PC_KEY_WORKDIR/export_staging_backup.sh" "$EXPORTER_PATH"
install -d -o root -g root -m 0700 "$SSH_DIR"
if [ ! -e "$AUTHORIZED_KEYS" ]; then
  install -o root -g root -m 0600 /dev/null "$AUTHORIZED_KEYS"
fi
chmod 0600 "$AUTHORIZED_KEYS"
if [ "$already_authorized" -eq 0 ]; then
  # Append without joining the new restriction onto a final existing key lacking LF.
  if [ -s "$AUTHORIZED_KEYS" ]; then
    last_byte="$(tail -c 1 "$AUTHORIZED_KEYS" | od -An -tu1 | tr -d '[:space:]')"
    [ "$last_byte" = 10 ] || printf '\n' >> "$AUTHORIZED_KEYS"
  fi
  printf '%s\n' "$FORCED_LINE" >> "$AUTHORIZED_KEYS"
  printf '%s\n' 'Dedicated read-only staging backup key added'
else
  printf '%s\n' 'Exact restricted key already present; no authorization was appended'
fi
