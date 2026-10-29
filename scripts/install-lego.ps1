param([string]$ArchivePath)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'lego-tools.ps1')
$root = Split-Path $PSScriptRoot -Parent
$toolFolder = Join-Path $root '.tools/lego/5.5.2'
if ($env:PROCESSOR_ARCHITECTURE -ne 'AMD64') { throw 'This pinned package is for Windows x64 only.' }
if (!$ArchivePath) {
    $downloadFolder = Join-Path $root '.cache/downloads'
    New-Item -ItemType Directory -Force -Path $downloadFolder | Out-Null
    $ArchivePath = Join-Path $downloadFolder 'lego_v5.5.2_windows_amd64.zip'
    Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/go-acme/lego/releases/download/v5.5.2/lego_v5.5.2_windows_amd64.zip' -OutFile $ArchivePath
}
Assert-LegoArchive $ArchivePath
if (Test-Path -LiteralPath $toolFolder) { throw 'Tool folder already exists; review it instead of overwriting.' }
New-Item -ItemType Directory -Force -Path $toolFolder | Out-Null
Expand-Archive -LiteralPath $ArchivePath -DestinationPath $toolFolder
if (!(Test-Path -LiteralPath (Join-Path $toolFolder 'lego.exe'))) { throw 'Expected executable missing.' }
Write-Output 'Lego 5.5.2 archive verified and extracted locally; no certificate requested.'
