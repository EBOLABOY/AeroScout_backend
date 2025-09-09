$ErrorActionPreference = 'Stop'

# Rollback imported users by ID list (reads from the JSON export)
# Usage: powershell -File scripts/rollback_auth_users.ps1 -File scripts/output/auth_import.json
param(
  [string]$File = 'scripts/output/auth_import.json'
)

if (-not (Test-Path $File)) { throw "File not found: $File" }

$envUrl = $env:SUPABASE_URL
$svcKey = $env:SUPABASE_SERVICE_ROLE_KEY
if (-not $envUrl -or -not $svcKey) { throw "Require SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in environment" }

$json = Get-Content -Raw -Path $File | ConvertFrom-Json
$ids = $json.users | ForEach-Object { $_.id }

Write-Host "Deleting" $ids.Count "users from auth.users ..."

foreach ($id in $ids) {
  $uri = "$envUrl/auth/v1/admin/users/$id"
  try {
    Invoke-WebRequest -UseBasicParsing -Uri $uri -Method DELETE -Headers @{ Authorization = "Bearer $svcKey" } -TimeoutSec 20 | Out-Null
    Write-Host " - Deleted" $id
  } catch {
    Write-Warning "Failed to delete $id : $($_.Exception.Message)"
  }
}

Write-Host "Rollback attempt completed"

