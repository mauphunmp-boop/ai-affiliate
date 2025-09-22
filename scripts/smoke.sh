#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"

usage() {
  cat <<EOF
Usage: $(basename "$0") [--run-ingest] [--check-legacy] [--merchant <slug>] [--campaign-id <id>]

Options:
  --run-ingest           Run a small ingest (/ingest/datafeeds/all, max_pages=1)
  --check-legacy         Verify legacy endpoints (should be 404 in this repo)
  --merchant <slug>      Filter ingest by merchant/campaign slug (e.g., tiki, lazada, tiktokshop)
  --campaign-id <id>     Force ingest for a specific campaign_id (active + approved)

Environment variables:
  BASE_URL               API base (default: http://localhost:8000)
  RUN_INGEST=1           Same as --run-ingest
  CHECK_LEGACY=1         Same as --check-legacy
EOF
}

MERCHANT="${MERCHANT:-}"
CAMPAIGN_ID="${CAMPAIGN_ID:-}"
PRESET=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-ingest) RUN_INGEST=1; shift ;;
    --check-legacy) CHECK_LEGACY=1; shift ;;
    --merchant) MERCHANT="$2"; shift 2 ;;
    --campaign-id) CAMPAIGN_ID="$2"; shift 2 ;;
  # no preset options
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1"; usage; exit 1 ;;
  esac
done

# presets removed; use --merchant instead

echo "==> Checking OpenAPI visible ingest endpoints"
curl -sS "$BASE_URL/openapi.json" | jq -r '.paths | keys[]' | grep -E '^/ingest/' || true

echo
if [[ "${CHECK_LEGACY:-0}" == "1" ]]; then
  echo "==> (Optional) Verifying legacy redirects (expect 308)"
  declare -A redirects=(
    ["/ingest/accesstrade/products"]="/ingest/products"
    ["/ingest/accesstrade/top-products"]="/ingest/top-products"
    ["/ingest/accesstrade/datafeeds/all"]="/ingest/datafeeds/all"
    ["/ingest/v2/campaigns/sync"]="/ingest/campaigns/sync"
    ["/ingest/v2/promotions"]="/ingest/promotions"
    ["/ingest/v2/top-products"]="/ingest/top-products"
  )

  failures=0
  for src in "${!redirects[@]}"; do
    want="${redirects[$src]}"
    echo -n " - POST $src -> Location: $want ... "
    status=$(curl -sSI -X POST "$BASE_URL$src" | awk 'NR==1{print $2}')
    loc=$(curl -sSI -X POST "$BASE_URL$src" | awk -F': ' 'tolower($1)=="location"{print $2}' | tr -d '\r')
    if [[ "$status" == "308" && "$loc" == "$want" ]]; then
      echo OK
    else
      echo "FAIL (status=$status, location=$loc)"; failures=$((failures+1))
    fi
  done
fi

echo
echo "==> Checking offers list (limit=1)"
first_id=$(curl -sS "$BASE_URL/offers?limit=1" | jq -r '.[0].id // empty')
if [[ -n "$first_id" ]]; then
  echo " - Found offer id: $first_id"
else
  echo " - No offers found. Tip: set RUN_INGEST=1 to ingest a small batch (max_pages=1)."
fi

if [[ "${RUN_INGEST:-0}" == "1" ]]; then
  echo
  echo "==> Attempting a small ingest: /ingest/datafeeds/all (max_pages=1)"
  # Build params
  params="{}"
  if [[ -n "$MERCHANT" || -n "$CAMPAIGN_ID" ]]; then
    # shell JSON builder using jq
    params=$(jq -n --arg m "$MERCHANT" --arg cid "$CAMPAIGN_ID" '
      ({} 
        + (if $m != "" then {merchant:$m} else {} end)
        + (if $cid != "" then {campaign_id:$cid} else {} end)
      )')
  fi

  payload=$(jq -n --argjson params "$params" '{
    provider: "accesstrade",
    max_pages: 1,
    limit_per_page: 100,
    check_urls: false,
    params: ( $params | (if .==null then {} else . end) )
  }')
  curl -sS -X POST "$BASE_URL/ingest/datafeeds/all" \
    -H 'content-type: application/json' \
    -d "$payload" | jq . || true

  echo "==> Re-checking offers list"
  first_id=$(curl -sS "$BASE_URL/offers?limit=1" | jq -r '.[0].id // empty')
  if [[ -n "$first_id" ]]; then
    echo " - Found offer id: $first_id"
  else
    echo " - Still no offers found. Check provider credentials/config and logs."
  fi
fi

echo
echo "==> Testing offers check endpoint"
test_id="${first_id:-1}"
curl -sS "$BASE_URL/offers/check/$test_id" | jq .

echo
echo "Smoke test finished."
