# Public integrity digest from the immutable official v5.5.2 Windows amd64 release.
$script:LegoArchiveSha256 = 'fc544130a2716329cad73a47b674e3aeea019c4753c3963d259bd45d946bbd34' # pragma: allowlist secret
function Assert-LegoArchive([string]$ArchivePath) {
    if ((Get-FileHash -LiteralPath $ArchivePath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $script:LegoArchiveSha256) {
        throw 'Lego archive checksum mismatch; nothing will be extracted or executed.'
    }
}
