#!/usr/bin/env bash
set -euo pipefail

echo "Exporting Poetry lock to requirements.lock.txt..."
poetry export -f requirements.txt --output requirements.lock.txt --without-hashes
echo "requirements.lock.txt generated successfully."

