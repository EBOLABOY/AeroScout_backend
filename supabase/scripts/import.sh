#!/usr/bin/env bash
set -euo pipefail

IN="users_for_import.jsonl"

if [[ ! -f "$IN" ]]; then
  echo "[error] Import file '$IN' not found. Run supabase/scripts/export.sh first." >&2
  exit 1
fi

if [[ -z "${SUPABASE_ACCESS_TOKEN:-}" ]]; then
  echo "[error] Please set SUPABASE_ACCESS_TOKEN for the Supabase CLI." >&2
  exit 1
fi

echo "⚠️  About to import users from $IN into Supabase Auth."
read -r -p "Proceed? (y/N): " REPLY
if [[ ! "$REPLY" =~ ^[Yy]$ ]]; then
  echo "Canceled."
  exit 1
fi

# Convert JSONL -> JSON { users: [...] } for supabase auth import
if ! command -v jq >/dev/null 2>&1; then
  echo "[error] jq is required to convert JSONL to JSON. Please install jq." >&2
  exit 1
fi

TMP_JSON="users_for_import.json"
jq -s '{users: .}' "$IN" > "$TMP_JSON"

echo "📦 Importing via Supabase CLI (auth import) ..."
npx -y supabase auth import --file "$TMP_JSON" --workdir .

echo "✅ Import command executed. Verify in Dashboard > Authentication > Users."

