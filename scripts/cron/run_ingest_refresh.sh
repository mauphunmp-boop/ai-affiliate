#!/usr/bin/env bash
set -euo pipefail

# Config
API_BASE_URL=${API_BASE_URL:-"http://localhost:8000"}
MAX_MINUTES=${MAX_MINUTES:-8}
LIMIT_PER_PAGE=${LIMIT_PER_PAGE:-100}
MAX_PAGES=${MAX_PAGES:-3}
THROTTLE_MS=${THROTTLE_MS:-50}
PAGE_CONCURRENCY=${PAGE_CONCURRENCY:-4}
INCLUDE_TOP=${INCLUDE_TOP:-false}

# Optional admin key
ADMIN_API_KEY_HEADER=()
if [[ -n "${ADMIN_API_KEY:-}" ]]; then
  ADMIN_API_KEY_HEADER=( -H "X-Admin-Key: ${ADMIN_API_KEY}" )
fi

# Jitter 0..90s để lệch pha với jobs khác
JITTER=$(( RANDOM % 91 ))
sleep "$JITTER"

BODY=$(cat <<JSON
{
  "max_minutes": ${MAX_MINUTES},
  "limit_per_page": ${LIMIT_PER_PAGE},
  "max_pages": ${MAX_PAGES},
  "throttle_ms": ${THROTTLE_MS},
  "page_concurrency": ${PAGE_CONCURRENCY},
  "include_top_products": ${INCLUDE_TOP}
}
JSON
)

curl -sS -X POST "${API_BASE_URL}/scheduler/ingest/refresh" \
  -H 'Content-Type: application/json' \
  "${ADMIN_API_KEY_HEADER[@]}" \
  -d "${BODY}" | jq -r '.'
