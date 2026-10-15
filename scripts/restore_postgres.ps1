#Requires -Version 7.0
param(
    [Parameter(Mandatory = $true)][string]$BackupFile,
    [Parameter(Mandatory = $true)][ValidatePattern('^[a-z0-9_-]+$')][string]$ComposeProject,
    [Parameter(Mandatory = $true)][ValidatePattern('^[A-Za-z0-9_]+$')][string]$ExpectedDatabase,
    [Parameter(Mandatory = $true)][string]$ConfirmRestore
)

$ErrorActionPreference = 'Stop'
if ($ConfirmRestore -cne "$ComposeProject/$ExpectedDatabase") {
    throw 'ConfirmRestore must equal project/database; no implicit production target is allowed'
}
if (-not (Test-Path -LiteralPath $BackupFile -PathType Leaf)) { throw 'Backup file not found' }
$backupPath = (Resolve-Path -LiteralPath $BackupFile).Path
if ((Get-Item -LiteralPath $backupPath).Length -eq 0) { throw 'Backup is empty' }
$checksumPath = "$backupPath.sha256"
if (-not (Test-Path -LiteralPath $checksumPath -PathType Leaf)) { throw 'Checksum sidecar is required' }
$sidecar = (Get-Content -LiteralPath $checksumPath -Raw).TrimEnd("`r", "`n")
$hash = (Get-FileHash -LiteralPath $backupPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($sidecar -cne "$hash  $([IO.Path]::GetFileName($backupPath))") {
    throw 'Backup checksum mismatch or invalid sidecar filename/format'
}

function Invoke-Docker {
    param([string[]]$DockerArgs)
    $output = & docker @DockerArgs
    if ($LASTEXITCODE -ne 0) { throw "Docker command failed (exit $LASTEXITCODE)" }
    return $output
}

# Binary streaming without cmd.exe or shell interpolation of file paths.
function Invoke-DockerWithBackup {
    param([string[]]$DockerArgs)
    $start = [Diagnostics.ProcessStartInfo]::new('docker')
    $start.UseShellExecute = $false
    $start.RedirectStandardInput = $true
    foreach ($argument in $DockerArgs) { $start.ArgumentList.Add($argument) }
    $process = [Diagnostics.Process]::Start($start)
    $stream = $null
    try {
        $stream = [IO.File]::OpenRead($backupPath)
        $stream.CopyTo($process.StandardInput.BaseStream)
        $process.StandardInput.Close()
        $process.WaitForExit()
        if ($process.ExitCode -ne 0) { throw "pg_restore failed (exit $($process.ExitCode))" }
    }
    finally {
        if ($stream) { $stream.Dispose() }
        $process.StandardInput.Close()
        if (-not $process.HasExited) { $process.WaitForExit() }
        $process.Dispose()
    }
}

$containers = @(Invoke-Docker -DockerArgs @('ps', '--filter', "label=com.docker.compose.project=$ComposeProject",
    '--filter', 'label=com.docker.compose.service=postgres', '--format', '{{.ID}}'))
if ($containers.Count -ne 1 -or -not $containers[0]) { throw 'Expected exactly one running postgres container for the explicit project' }
$container = $containers[0].Trim()
$database = Invoke-Docker -DockerArgs @('exec', $container, 'printenv', 'POSTGRES_DB')
if ($database -cne $ExpectedDatabase) { throw 'Target database does not match ExpectedDatabase' }

$emptyQuery = @'
SELECT
 (SELECT count(*) FROM pg_namespace WHERE nspname NOT IN ('public','information_schema') AND nspname !~ '^pg_') +
 (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname != 'information_schema' AND n.nspname !~ '^pg_') +
 (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname != 'information_schema' AND n.nspname !~ '^pg_') +
 (SELECT count(*) FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace WHERE n.nspname != 'information_schema' AND n.nspname !~ '^pg_');
'@
$count = Invoke-Docker -DockerArgs @('exec', $container, 'sh', '-c',
    'exec psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "$1"', 'sh', $emptyQuery)
if ($count -cne '0') { throw 'Target database is not empty; refusing to overwrite existing data' }
Invoke-DockerWithBackup -DockerArgs @('exec', '-i', $container, 'sh', '-c', 'exec pg_restore --list > /dev/null')
Invoke-DockerWithBackup -DockerArgs @('exec', '-i', $container, 'sh', '-c',
    'exec pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --single-transaction --exit-on-error --no-owner --no-acl')
Write-Host "Restore completed into $ComposeProject/$database"
