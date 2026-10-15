#!/usr/bin/env sh
# Apply the approved daily/7 policy to the existing Buy Modern staging service.
set -eu
[ "$(id -u)" -eq 0 ] || { echo 'Run as root on the staging host' >&2; exit 1; }
command -v curl docker flock sha256sum systemctl systemd-analyze readlink install > /dev/null
: "${STAGING_TOOLING_REF:?Укажите полный SHA tooling commit из handoff}"
case "$STAGING_TOOLING_REF" in *[!0-9a-f]*) exit 1;; esac
test "${#STAGING_TOOLING_REF}" -eq 40
grep -qx 'BACKUP_COMPOSE_PROJECT=l4w4kssko4ogk00sg8co480s' /etc/buy-modern/staging-backup.env
grep -qx 'BACKUP_DIR=/var/backups/buy-staging' /etc/buy-modern/staging-backup.env
for STAGING_POLICY_KEY in BACKUP_COMPOSE_PROJECT BACKUP_DIR BACKUP_RETENTION_DAYS; do
  test "$(grep -c "^[[:space:]]*$STAGING_POLICY_KEY[[:space:]]*=" /etc/buy-modern/staging-backup.env)" -eq 1
done
test "$(readlink -f /var/backups/buy-staging)" = /var/backups/buy-staging
test "$(docker ps -q --filter label=com.docker.compose.project=l4w4kssko4ogk00sg8co480s --filter label=com.docker.compose.service=postgres | wc -l)" -eq 1
STAGING_PREVIOUS_SCRIPT_SHA="$(sha256sum /opt/buy-modern/current/scripts/backup_postgres.sh)"
STAGING_PREVIOUS_SCRIPT_SHA="${STAGING_PREVIOUS_SCRIPT_SHA%% *}"
case "$STAGING_PREVIOUS_SCRIPT_SHA" in
  7be7ccfbb2a0200a3fb1f28ec48840eaf114016303b80df46cac56605a9791d6|859878ee44d3413bb181379c1bbfd8ebe9767b64a29f6c68e63569ba3ba16238) ;;
  *) echo 'Installed backup script differs from the approved versions; refusing to overwrite' >&2; exit 1;;
esac
STAGING_POLICY_DIR="$(mktemp -d /tmp/buy-staging-daily.XXXXXX)"
STAGING_POLICY_SOURCE="https://raw.githubusercontent.com/EgorArutiunean/faethon-system/$STAGING_TOOLING_REF"
curl --fail --show-error --silent --location "$STAGING_POLICY_SOURCE/scripts/backup_postgres.sh" --output "$STAGING_POLICY_DIR/backup_postgres.sh"
curl --fail --show-error --silent --location "$STAGING_POLICY_SOURCE/ops/systemd/buy-modern-staging-backup.timer" --output "$STAGING_POLICY_DIR/buy-modern-staging-backup.timer"
(
  cd "$STAGING_POLICY_DIR"
  printf '%s\n' \
    '859878ee44d3413bb181379c1bbfd8ebe9767b64a29f6c68e63569ba3ba16238  backup_postgres.sh' \
    '9c38b5c5c7ed2de664aa517ec16f7252610242d1adb55ea86fa6c362e1febea0  buy-modern-staging-backup.timer' | sha256sum -c -
)
sh -n "$STAGING_POLICY_DIR/backup_postgres.sh"
systemd-analyze verify "$STAGING_POLICY_DIR/buy-modern-staging-backup.timer"
sed 's/^BACKUP_RETENTION_DAYS=[0-9][0-9]*$/BACKUP_RETENTION_DAYS=7/' /etc/buy-modern/staging-backup.env > "$STAGING_POLICY_DIR/staging-backup.env"
grep -qx 'BACKUP_RETENTION_DAYS=7' "$STAGING_POLICY_DIR/staging-backup.env"
cp -p /opt/buy-modern/current/scripts/backup_postgres.sh "$STAGING_POLICY_DIR/backup_postgres.before.sh"
cp -p /etc/systemd/system/buy-modern-staging-backup.timer "$STAGING_POLICY_DIR/backup.before.timer"
cp -p /etc/buy-modern/staging-backup.env "$STAGING_POLICY_DIR/backup.before.env"
systemctl stop buy-modern-staging-backup.timer
install -o root -g root -m 0644 "$STAGING_POLICY_DIR/backup_postgres.sh" /opt/buy-modern/current/scripts/backup_postgres.sh
install -o root -g root -m 0644 "$STAGING_POLICY_DIR/buy-modern-staging-backup.timer" /etc/systemd/system/buy-modern-staging-backup.timer
install -o root -g root -m 0600 "$STAGING_POLICY_DIR/staging-backup.env" /etc/buy-modern/staging-backup.env
systemctl daemon-reload
systemctl enable --now buy-modern-staging-backup.timer
systemctl list-timers buy-modern-staging-backup.timer --all --no-pager
grep '^BACKUP_RETENTION_DAYS=' /etc/buy-modern/staging-backup.env
printf 'Previous configuration saved in: %s\n' "$STAGING_POLICY_DIR"
