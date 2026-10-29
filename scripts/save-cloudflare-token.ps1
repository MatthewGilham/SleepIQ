param([switch]$Rotate)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'private-folders.ps1')
$dataRoot = Join-Path $env:LOCALAPPDATA 'SleepIQ'
Assert-PrivateFolder $dataRoot
$security = Join-Path $dataRoot 'security'
if (!(Test-Path -LiteralPath $security)) { New-Item -ItemType Directory -Path $security | Out-Null }
Assert-PrivateFolder $security
$destination = Join-Path $security 'cloudflare-token.dpapi'
if ((Test-Path -LiteralPath $destination) -and !$Rotate) {
    throw 'Token already stored. Revoke the old token first, then use -Rotate for explicit replacement.'
}
if ($Rotate -and !(Test-Path -LiteralPath $destination)) {
    throw 'No stored token to rotate; run without -Rotate for initial storage.'
}
$token = Read-Host 'Paste your zone-restricted Cloudflare token here (hidden; never into chat)' -AsSecureString
if ($token.Length -lt 20) { throw 'Token appears incomplete; nothing saved.' }
$encrypted = ConvertFrom-SecureString $token
$temporary = Join-Path $security ('token-' + [guid]::NewGuid().ToString('N') + '.tmp')
try {
    [IO.File]::WriteAllText($temporary, $encrypted)
    if ($Rotate) {
        [IO.File]::Replace($temporary, $destination, [NullString]::Value)
    } else {
        [IO.File]::Move($temporary, $destination)
    }
} finally {
    if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary }
}
Write-Output 'Cloudflare token saved using Windows user encryption; token was not printed.'
