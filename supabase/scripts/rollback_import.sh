#!/usr/bin/env bash
set -euo pipefail

IN="users_for_import.jsonl"

if [[ ! -f "$IN" ]]; then
  echo "[error] '$IN' not found; cannot rollback." >&2
  exit 1
fi

if [[ -z "${SUPABASE_URL:-}" || -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]]; then
  echo "[error] Require SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY for Admin API." >&2
  exit 1
fi

echo "🔥 This will delete imported users listed in $IN from auth.users!"
read -r -p "Dangerous operation. Continue? (y/N): " REPLY
if [[ ! "$REPLY" =~ ^[Yy]$ ]]; then
  echo "Canceled."
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "[error] jq is required to parse JSONL." >&2
  exit 1
fi

COUNT=0
while IFS= read -r line; do
  ID=$(echo "$line" | jq -r '.id')
  if [[ -n "$ID" && "$ID" != "null" ]]; then
    URI="${SUPABASE_URL%/}/auth/v1/admin/users/$ID"
    http_code=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "$URI" \
      -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY")
    if [[ "$http_code" == "204" || "$http_code" == "200" ]]; then
      echo " - Deleted $ID"
      COUNT=$((COUNT+1))
    else
      echo " ! Failed to delete $ID (HTTP $http_code)" >&2
    fi
  fi
done < "$IN"

echo "✅ Rollback completed; deleted $COUNT users."

