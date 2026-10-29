param(
    [Parameter(Mandatory = $true)][string]$ExportPath,
    [string]$DataRoot = (Join-Path $env:LOCALAPPDATA 'SleepIQ'),
    [string]$BackupRoot = 'C:\Users\Matth\SleepIQ-Backups',
    [switch]$Migrate
)
# Owner-run import of ONE explicitly chosen export into the private store. Prints counts only.
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'private-folders.ps1')
$previousPythonPath = $env:PYTHONPATH
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    foreach ($folder in @($DataRoot, $BackupRoot, (Join-Path $DataRoot 'raw'))) {
        Assert-PrivateFolder $folder
    }
    $env:PYTHONPATH = Join-Path (Get-Location) 'backend'
    $arguments = @('-m', 'app.ingest.cli', '--data-root', $DataRoot, '--backups', $BackupRoot, '--file', $ExportPath)
    if ($Migrate) { $arguments += '--migrate' }
    & .\.venv\Scripts\python.exe @arguments
    if ($LASTEXITCODE) { throw 'Import failed. Nothing was partially stored; no export contents were printed.' }
} finally {
    $env:PYTHONPATH = $previousPythonPath
    Pop-Location
}
