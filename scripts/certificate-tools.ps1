# Shared helpers for certificate status and renewal (P25). Dot-source; reads only the PUBLIC certificate.
$script:CertificateHost = 'sync.mgilham.online'

function Get-CertificateInfo([string]$Path) {
    $cert = New-Object Security.Cryptography.X509Certificates.X509Certificate2($Path)
    try {
        [pscustomobject]@{
            Hostname  = $cert.GetNameInfo([Security.Cryptography.X509Certificates.X509NameType]::DnsName, $false)
            NotBefore = $cert.NotBefore.ToUniversalTime()
            NotAfter  = $cert.NotAfter.ToUniversalTime()
        }
    } finally { $cert.Dispose() }
}

function Test-RenewalDue([datetime]$NotAfterUtc, [datetime]$NowUtc, [int]$Days) {
    return (($NotAfterUtc - $NowUtc).TotalDays -le $Days)
}

function Format-UtcStamp([datetime]$Value) { $Value.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ') }

# Writes security/certificate-status.json atomically. Holds dates and a result word only: no keys, tokens or tool output.
# Without -Result/-Attempt the previous attempt fields are kept, so a plain refresh never hides an earlier failure.
function Write-CertificateStatus([string]$SecurityFolder, [string]$CertificatePath, [string]$Result, [datetime]$Attempt) {
    $target = Join-Path $SecurityFolder 'certificate-status.json'
    $previous = @{ last_result = 'none'; last_attempt_utc = $null }
    if (Test-Path -LiteralPath $target) {
        try {
            $old = Get-Content -Raw -LiteralPath $target | ConvertFrom-Json
            if ($old.last_result) { $previous.last_result = [string]$old.last_result }
            if ($old.last_attempt_utc) { $previous.last_attempt_utc = [string]$old.last_attempt_utc }
        } catch { }
    }
    if ($Result) { $previous.last_result = $Result }
    if ($Attempt) { $previous.last_attempt_utc = Format-UtcStamp $Attempt }
    $info = Get-CertificateInfo $CertificatePath
    $body = [ordered]@{
        hostname         = $info.Hostname
        not_after_utc    = Format-UtcStamp $info.NotAfter
        checked_utc      = Format-UtcStamp ([DateTime]::UtcNow)
        last_result      = $previous.last_result
        last_attempt_utc = $previous.last_attempt_utc
    } | ConvertTo-Json
    $temporary = "$target.$([guid]::NewGuid().ToString('N')).tmp"
    try {
        [IO.File]::WriteAllText($temporary, $body, (New-Object Text.UTF8Encoding($false)))
        Move-Item -LiteralPath $temporary -Destination $target -Force
    } finally { Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue }
}
