#!/usr/bin/env bash
set -euo pipefail

# Migrate Docker data-root from /var/lib/docker to /data/docker with minimal downtime.
# - Stops Docker, rsyncs data, updates /etc/docker/daemon.json, restarts Docker.
# - Keeps a backup of the old directory for manual deletion later.
#
# Usage:
#   sudo bash scripts/migrate_docker_to_data.sh
#
# Notes:
# - Requires root/sudo privileges
# - Ensure /data has enough free space (Docker currently uses tens of GB)

require_root() {
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    echo "This script must be run as root (use sudo)" >&2
    exit 1
  fi
}

timestamp() { date +%Y%m%d-%H%M%S; }

main() {
  require_root

  local SRC=/var/lib/docker
  local DEST=/data/docker
  local DAEMON_JSON=/etc/docker/daemon.json
  local BACKUP_SRC="/var/lib/docker.backup.$(timestamp)"
  local BACKUP_DAEMON_JSON="/etc/docker/daemon.json.backup.$(timestamp)"

  if [[ ! -d /data ]]; then
    echo "Error: /data does not exist. Create and mount a larger partition at /data first." >&2
    exit 1
  fi

  mkdir -p "$DEST"

  echo "[1/6] Checking current Docker root..."
  if command -v docker >/dev/null 2>&1; then
    docker info 2>/dev/null | sed -n 's/^ Docker Root Dir: //p' | sed 's/^/  current: /' || true
  else
    echo "  docker not found in PATH; proceeding"
  fi

  echo "[2/6] Stopping Docker service..."
  systemctl stop docker

  echo "[3/6] Syncing $SRC -> $DEST ... (this may take a while)"
  rsync -aHAX --numeric-ids "$SRC/" "$DEST/"

  echo "[4/6] Updating $DAEMON_JSON (backup: $BACKUP_DAEMON_JSON)"
  if [[ -f "$DAEMON_JSON" ]]; then
    cp -a "$DAEMON_JSON" "$BACKUP_DAEMON_JSON"
  fi
  # Write minimal daemon.json with data-root. If you have additional settings, merge manually from the backup.
  printf '{
  "data-root": "/data/docker"
}
' > "$DAEMON_JSON"

  echo "[5/6] Starting Docker service..."
  systemctl start docker
  sleep 1

  echo "Verifying new Docker Root Dir:"
  local ROOT_DIR
  ROOT_DIR=$(docker info 2>/dev/null | sed -n 's/^ Docker Root Dir: //p') || true
  echo "  reported: ${ROOT_DIR:-unknown}"
  if [[ "$ROOT_DIR" != "/data/docker" ]]; then
    echo "Error: Docker Root Dir is not /data/docker. Rolling back service state; manual intervention required." >&2
    systemctl status docker --no-pager || true
    exit 1
  fi

  echo "[6/6] Keeping backup of old data at $BACKUP_SRC"
  mv "$SRC" "$BACKUP_SRC"
  mkdir -p "$SRC"
  echo "Success. Old data preserved at: $BACKUP_SRC"
  echo "You may delete the backup after verification to reclaim space, e.g.: rm -rf $BACKUP_SRC"
}

main "$@"
