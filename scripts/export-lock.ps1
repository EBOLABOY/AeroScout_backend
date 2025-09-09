# Requires: Poetry installed (`pipx install poetry` or `pip install poetry`)
# Usage: ./scripts/export-lock.ps1

Write-Host "Exporting Poetry lock to requirements.lock.txt..." -ForegroundColor Cyan
poetry export -f requirements.txt --output requirements.lock.txt --without-hashes
if ($LASTEXITCODE -eq 0) {
  Write-Host "requirements.lock.txt generated successfully." -ForegroundColor Green
} else {
  Write-Host "Failed to export lockfile." -ForegroundColor Red
  exit 1
}

