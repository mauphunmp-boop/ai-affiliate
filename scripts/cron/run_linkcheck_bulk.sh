#!/usr/bin/env bash
set -euo pipefail

# Bulk runner to sweep multiple slices in one go (e.g., daily delete at 3AM)
# Usage:
#   API_BASE=http://localhost:8000 COUNT=20 DELETE_DEAD=1 ./scripts/cron/run_linkcheck_bulk.sh
# Env:
#   API_BASE     - API base URL (required)
#   COUNT        - number of times to call rotate (default: 20)
#   DELETE_DEAD  - 0/1 to pass delete flag to run_linkcheck.sh (default: 0)

API_BASE=${API_BASE:-}
if [[ -z "${API_BASE}" ]]; then
  echo "[bulk] ERROR: API_BASE is required" >&2
  exit 1
fi
COUNT=${COUNT:-20}
DELETE_DEAD=${DELETE_DEAD:-0}

for ((i=1;i<=COUNT;i++)); do
  echo "[bulk] pass $i/${COUNT}"
  API_BASE="${API_BASE}" DELETE_DEAD="${DELETE_DEAD}" \
    "$(dirname "$0")/run_linkcheck.sh"
  sleep 2
done
