$ErrorActionPreference = 'Stop'

# Usage: powershell -ExecutionPolicy Bypass -File scripts/auth_import.ps1 -File scripts/output/auth_import.json
param(
  [string]$File = 'scripts/output/auth_import.json'
)

Write-Host "Using import file: $File"

# Ensure proxy if needed
if ($env:HTTP_PROXY -or $env:HTTPS_PROXY) {
  Write-Host "Proxy configured: HTTP=$env:HTTP_PROXY HTTPS=$env:HTTPS_PROXY"
}

if (-not (Test-Path $File)) {
  throw "Import file not found: $File"
}

# Requires project to be linked and SUPABASE_ACCESS_TOKEN set
npx -y supabase auth import --file $File --workdir .

