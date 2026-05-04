param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile,
    [string]$ComposeFile = "docker-compose.prod.yml"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $BackupFile)) {
    throw "Backup file not found: $BackupFile"
}

$backupPath = (Resolve-Path -LiteralPath $BackupFile).Path
cmd /c "docker compose -f `"$ComposeFile`" exec -T postgres sh -c 'pg_restore -U `"`$POSTGRES_USER`" -d `"`$POSTGRES_DB`" --clean --if-exists --no-owner' < `"$backupPath`""

Write-Host "Restore completed from $BackupFile"
