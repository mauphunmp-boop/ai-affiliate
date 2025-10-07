#!/usr/bin/env bash
set -euo pipefail

# Simple disk usage monitor. Alerts if / or /data exceed thresholds.
# Usage: ./disk_check.sh [threshold_root%] [threshold_data%]
# Defaults: 85% for / and 90% for /data

THRESH_ROOT=${1:-85}
THRESH_DATA=${2:-90}

alert() {
  echo "[disk_check] $(date -Is) $1" >&2
}

usage_of() {
  df -P $1 | awk 'NR==2 {gsub("%","",$5); print $5}'
}

ROOT_USE=$(usage_of /)
DATA_USE=$(usage_of /data || echo 0)

if [ "$ROOT_USE" -ge "$THRESH_ROOT" ]; then
  alert "/ usage ${ROOT_USE}% >= ${THRESH_ROOT}%"
fi

if mountpoint -q /data && [ "$DATA_USE" -ge "$THRESH_DATA" ]; then
  alert "/data usage ${DATA_USE}% >= ${THRESH_DATA}%"
fi

exit 0
