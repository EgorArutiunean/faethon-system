param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile,
    [string]$ComposeFile = "docker-compose.prod.yml",
    [string]$EnvFile = ".env.production"
)

$ErrorActionPreference = "Stop"

function Get-ContainerEnvValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $rawValue = & docker compose --env-file $EnvFile -f $ComposeFile exec -T postgres printenv $Name
    if ($LASTEXITCODE -ne 0) {
        throw "Cannot read $Name from the PostgreSQL container"
    }
    $value = ($rawValue | Out-String).Trim()
    if (-not $value) {
        throw "Variable $Name is empty in the PostgreSQL container"
    }
    if ($value -notmatch '^[A-Za-z_][A-Za-z0-9_-]*$') {
        throw "Variable $Name must be a safe PostgreSQL identifier"
    }
    return $value
}

if (-not (Test-Path -LiteralPath $BackupFile)) {
    throw "Backup file not found: $BackupFile"
}
if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
    throw "Environment file not found: $EnvFile"
}

$postgresUser = Get-ContainerEnvValue -Name "POSTGRES_USER"
$postgresDatabase = Get-ContainerEnvValue -Name "POSTGRES_DB"

$backupPath = (Resolve-Path -LiteralPath $BackupFile).Path
$checksumPath = "$backupPath.sha256"
if (Test-Path -LiteralPath $checksumPath -PathType Leaf) {
    $expectedChecksum = ((Get-Content -LiteralPath $checksumPath -Raw).Trim() -split '\s+')[0]
    $actualChecksum = (Get-FileHash -LiteralPath $backupPath -Algorithm SHA256).Hash
    if ($actualChecksum -ine $expectedChecksum) {
        throw "Backup checksum mismatch: $BackupFile"
    }
}

cmd /d /s /c "docker compose --env-file `"$EnvFile`" -f `"$ComposeFile`" exec -T postgres pg_restore --list < `"$backupPath`" > NUL"
if ($LASTEXITCODE -ne 0) {
    throw "Backup validation failed with exit code $LASTEXITCODE"
}

cmd /d /s /c "docker compose --env-file `"$EnvFile`" -f `"$ComposeFile`" exec -T postgres pg_restore -U `"$postgresUser`" -d `"$postgresDatabase`" --clean --if-exists --no-owner < `"$backupPath`""
if ($LASTEXITCODE -ne 0) {
    throw "Restore failed with exit code $LASTEXITCODE"
}

Write-Host "Restore completed from $BackupFile"
