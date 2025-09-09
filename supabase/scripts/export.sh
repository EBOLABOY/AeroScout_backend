#!/usr/bin/env bash
set -euo pipefail

# Ensure SUPABASE_DB_URL is set to your remote Postgres URL
if [[ -z "${SUPABASE_DB_URL:-}" ]]; then
  echo "[error] Please set SUPABASE_DB_URL (postgresql://...@.../postgres)" >&2
  exit 1
fi

OUT="users_for_import.jsonl"
SQL_FILE="supabase/scripts/export_users.sql"

echo "🚀 Exporting users from public.profiles to $OUT ..."

# -A: unaligned, -t: tuples only (no headers), -X: no .psqlrc, -v ON_ERROR_STOP to fail fast
psql -X -v ON_ERROR_STOP=1 -A -t "$SUPABASE_DB_URL" -f "$SQL_FILE" > "$OUT"

LINES=$(wc -l < "$OUT" | tr -d ' ')
echo "✅ Exported $LINES users -> $OUT"

