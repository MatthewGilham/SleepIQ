param([Parameter(Mandatory=$true)][string]$Destination)
$ErrorActionPreference = 'Stop'
# All objects are ephemeral: no certificate-store, trust, DNS or listener changes.
$csp = [Security.Cryptography.CspParameters]::new()
$csp.Flags = [Security.Cryptography.CspProviderFlags]::CreateEphemeralKey
$rootKey = [Security.Cryptography.RSACryptoServiceProvider]::new(2048, $csp)
$leafKey = [Security.Cryptography.RSACryptoServiceProvider]::new(2048, $csp)
$padding = [Security.Cryptography.RSASignaturePadding]::Pkcs1
$hash = [Security.Cryptography.HashAlgorithmName]::SHA256
$root = $null
try {
    $rootRequest = [Security.Cryptography.X509Certificates.CertificateRequest]::new(
        'CN=SleepIQ synthetic test root', $rootKey, $hash, $padding)
    $rootRequest.CertificateExtensions.Add(
        [Security.Cryptography.X509Certificates.X509BasicConstraintsExtension]::new($true, $false, 0, $true))
    $rootRequest.CertificateExtensions.Add(
        [Security.Cryptography.X509Certificates.X509KeyUsageExtension]::new(
            [Security.Cryptography.X509Certificates.X509KeyUsageFlags]::KeyCertSign, $true))
    $now = [DateTimeOffset]::UtcNow
    $root = $rootRequest.CreateSelfSigned($now.AddDays(-30), $now.AddYears(10))
    $request = [Security.Cryptography.X509Certificates.CertificateRequest]::new(
        'CN=sync.mgilham.online', $leafKey, $hash, $padding)
    $san = [Security.Cryptography.X509Certificates.SubjectAlternativeNameBuilder]::new()
    $san.AddDnsName('sync.mgilham.online')
    $request.CertificateExtensions.Add($san.Build())
    $request.CertificateExtensions.Add(
        [Security.Cryptography.X509Certificates.X509BasicConstraintsExtension]::new($false, $false, 0, $true))
    function Write-PublicPem($Certificate, [string]$Name) {
        $base64 = [Convert]::ToBase64String($Certificate.RawData, [Base64FormattingOptions]::InsertLineBreaks)
        $text = "-----BEGIN CERTIFICATE-----" + [Environment]::NewLine + $base64 +
            [Environment]::NewLine + "-----END CERTIFICATE-----" + [Environment]::NewLine
        [IO.File]::WriteAllText((Join-Path $Destination $Name), $text)
    }
    Write-PublicPem $root 'root.crt'
    $valid = $request.Create($root, $now.AddDays(-1), $now.AddDays(365), [byte[]]@(1))
    try { Write-PublicPem $valid 'sync.mgilham.online.crt' } finally { $valid.Dispose() }
    $expired = $request.Create($root, $now.AddDays(-3), $now.AddDays(-2), [byte[]]@(2))
    try { Write-PublicPem $expired 'expired.crt' } finally { $expired.Dispose() }
    $parameters = $leafKey.ExportParameters($true)
    $values = @{}
    foreach ($name in @('Modulus', 'Exponent', 'D', 'P', 'Q', 'DP', 'DQ', 'InverseQ')) {
        $values[$name] = [Convert]::ToBase64String($parameters.$name)
    }
    [IO.File]::WriteAllText((Join-Path $Destination 'synthetic-key.json'), ($values | ConvertTo-Json))
} finally {
    if ($root) { $root.Dispose() }
    $rootKey.Dispose()
    $leafKey.Dispose()
}
