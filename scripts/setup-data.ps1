param(
    [string]$DataRoot = (Join-Path $env:LOCALAPPDATA 'SleepIQ'),
    [string]$BackupRoot = 'C:\Users\Matth\SleepIQ-Backups'
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'private-folders.ps1')
$previousPythonPath = $env:PYTHONPATH
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    # No elevation, ACL changes or existing-data migration. Stop on ambiguous existing state.
    if (Test-Path -LiteralPath (Join-Path $DataRoot 'sleepiq.sqlite3')) {
        throw 'Database already exists. Setup stopped without migrating or overwriting it.'
    }
    foreach ($folder in @($DataRoot, $BackupRoot)) {
        if (!(Test-Path -LiteralPath $folder)) {
            New-Item -ItemType Directory -Path $folder | Out-Null
        }
        Assert-PrivateFolder $folder
    }
    $env:PYTHONPATH = Join-Path (Get-Location) 'backend'
    & .\.venv\Scripts\python.exe -m app.db.initialize --data-root $DataRoot
    if ($LASTEXITCODE) { throw 'Data initialization failed; no existing database was overwritten.' }
    Assert-PrivateFolder (Join-Path $DataRoot 'raw')
    & .\.venv\Scripts\python.exe -m app.db.backup_cli daily --database (Join-Path $DataRoot 'sleepiq.sqlite3') --raw (Join-Path $DataRoot 'raw') --backups $BackupRoot
    if ($LASTEXITCODE) { throw 'Initial backup failed; source data is preserved.' }
    Write-Output 'Private data folders and the initial empty database backup are ready.'
} finally {
    $env:PYTHONPATH = $previousPythonPath
    Pop-Location
}
