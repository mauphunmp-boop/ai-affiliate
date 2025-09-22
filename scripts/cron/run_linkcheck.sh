#!/usr/bin/env bash
set -euo pipefail

# Run the rotate link-check endpoint with delete enabled.
# Usage:
#   API_BASE="http://localhost:8000" ./scripts/cron/run_linkcheck.sh
# Optional:
#   API_TOKEN="<bearer-token>" (if your API behind auth)
#   TIMEOUT="20" (seconds)
#   RETRIES="2"  (curl --retry count)

API_BASE=${API_BASE:-${1:-}}
if [[ -z "${API_BASE}" ]]; then
  echo "[linkcheck] ERROR: API_BASE is required (e.g., http://localhost:8000)" >&2
  exit 1
fi

TIMEOUT=${TIMEOUT:-20}
RETRIES=${RETRIES:-2}
DELETE_DEAD=${DELETE_DEAD:-0}
URL_BASE="${API_BASE%/}/scheduler/linkcheck/rotate"
if [[ "${DELETE_DEAD}" == "1" ]]; then
  URL="${URL_BASE}?delete_dead=true"
else
  URL="${URL_BASE}"
fi

HDR_AUTH=()
if [[ -n "${API_TOKEN:-}" ]]; then
  HDR_AUTH=(-H "Authorization: Bearer ${API_TOKEN}")
fi

ts() { date '+%Y-%m-%d %H:%M:%S'; }
echo "[$(ts)] linkcheck rotate → ${URL} (delete=${DELETE_DEAD})"

set +e
OUT=$(curl -sS -X POST "${URL}" \
  -H 'Content-Type: application/json' \
  "${HDR_AUTH[@]}" \
  --max-time "${TIMEOUT}" \
  --retry "${RETRIES}" \
  --retry-delay 2 \
  --fail)
CODE=$?
set -e

if [[ ${CODE} -ne 0 ]]; then
  echo "[$(ts)] linkcheck FAILED (exit=${CODE})" >&2
  exit ${CODE}
fi

echo "[$(ts)] linkcheck OK: ${OUT}"
