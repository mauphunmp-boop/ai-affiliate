#!/usr/bin/env bash
set -euo pipefail

# Cloudflare DNS CNAME creator/updater via API v4
# Idempotent: create if missing, update if exists, optional proxied flag
#
# Requirements:
#   - curl, jq
#   - Environment variables:
#       CF_API_TOKEN   : Cloudflare API token with Zone.DNS:Edit
#       CF_ZONE_ID     : Cloudflare Zone ID (for tuvanmuasam.app)
#   - Arguments:
#       --name <subdomain>       # e.g. www
#       --target <cname-target>  # e.g. 73562cac-...cfargotunnel.com
#       [--ttl <seconds>]        # default 300 (1..86400, 1 means Auto in UI)
#       [--proxied <true|false>] # default true
#       [--dry-run]              # no changes, print intended actions
#
# Example:
#   CF_API_TOKEN=... CF_ZONE_ID=... \
#   ./scripts/cloudflare_dns_cname.sh --name www \
#     --target 73562cac-cd50-443e-a416-6281a5655968.cfargotunnel.com \
#     --ttl 300 --proxied true

usage() {
  cat <<'USAGE'
Usage: cloudflare_dns_cname.sh --name <sub> --target <fqdn> [--ttl <sec>] [--proxied <true|false>] [--dry-run]

Environment:
  CF_API_TOKEN   Cloudflare API token (Zone.DNS:Edit)
  CF_ZONE_ID     Cloudflare Zone ID
USAGE
}

if [[ ${1:-} == "-h" || ${1:-} == "--help" ]]; then
  usage
  exit 0
fi

# Defaults
TTL=300
PROXIED=true
DRY_RUN=false
NAME=""
TARGET=""

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --name) NAME="$2"; shift 2;;
    --target) TARGET="$2"; shift 2;;
    --ttl) TTL="$2"; shift 2;;
    --proxied) PROXIED="$2"; shift 2;;
    --dry-run) DRY_RUN=true; shift;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2;;
  esac
done

: "${CF_API_TOKEN:?CF_API_TOKEN is required}"
: "${CF_ZONE_ID:?CF_ZONE_ID is required}"

if [[ -z "$NAME" || -z "$TARGET" ]]; then
  echo "--name and --target are required" >&2
  usage
  exit 2
fi

API="https://api.cloudflare.com/client/v4"
AUTH=( -H "Authorization: Bearer ${CF_API_TOKEN}" -H "Content-Type: application/json" )

# Fetch existing record if any
set +e
EXISTING_JSON=$(curl -fsS "${API}/zones/${CF_ZONE_ID}/dns_records?type=CNAME&name=${NAME}" "${AUTH[@]}")
RC=$?
set -e
if [[ $RC -ne 0 ]]; then
  echo "Error querying DNS records (HTTP)" >&2
  exit $RC
fi

EXISTING_ID=$(echo "$EXISTING_JSON" | jq -r '.result[0].id // empty')
EXISTING_CONTENT=$(echo "$EXISTING_JSON" | jq -r '.result[0].content // empty')
EXISTING_PROXIED=$(echo "$EXISTING_JSON" | jq -r '.result[0].proxied // empty')

BODY=$(jq -n --arg type CNAME --arg name "$NAME" --arg content "$TARGET" \
             --argjson ttl "$TTL" --argjson proxied $( [[ "$PROXIED" == "true" ]] && echo true || echo false ) \
             '{type:$type,name:$name,content:$content,ttl:$ttl,proxied:$proxied}')

if [[ -n "$EXISTING_ID" ]]; then
  # Update if any field differs
  if [[ "$EXISTING_CONTENT" == "$TARGET" && "$EXISTING_PROXIED" == "$PROXIED" ]]; then
    echo "No change: CNAME ${NAME} already points to ${TARGET} (proxied=${EXISTING_PROXIED})"
    exit 0
  fi
  echo "Updating CNAME ${NAME} -> ${TARGET} (proxied=${PROXIED}, ttl=${TTL})"
  if [[ "$DRY_RUN" == true ]]; then
    echo "DRY-RUN: PATCH ${API}/zones/${CF_ZONE_ID}/dns_records/${EXISTING_ID}"
    echo "$BODY" | jq .
    exit 0
  fi
  RESP=$(curl -fsS -X PATCH "${API}/zones/${CF_ZONE_ID}/dns_records/${EXISTING_ID}" "${AUTH[@]}" --data "$BODY")
  echo "$RESP" | jq .
  if [[ $(echo "$RESP" | jq -r '.success') != "true" ]]; then
    echo "Update failed" >&2
    exit 1
  fi
else
  echo "Creating CNAME ${NAME} -> ${TARGET} (proxied=${PROXIED}, ttl=${TTL})"
  if [[ "$DRY_RUN" == true ]]; then
    echo "DRY-RUN: POST ${API}/zones/${CF_ZONE_ID}/dns_records"
    echo "$BODY" | jq .
    exit 0
  fi
  RESP=$(curl -fsS -X POST "${API}/zones/${CF_ZONE_ID}/dns_records" "${AUTH[@]}" --data "$BODY")
  echo "$RESP" | jq .
  if [[ $(echo "$RESP" | jq -r '.success') != "true" ]]; then
    echo "Create failed" >&2
    exit 1
  fi
fi

echo "Done."
