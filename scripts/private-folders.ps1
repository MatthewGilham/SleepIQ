function Assert-PrivateFolder([string]$Path) {
    $folder = Get-Item -LiteralPath $Path -ErrorAction Stop
    if (!$folder.PSIsContainer -or ($folder.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw "A regular private directory is required."
    }
    $allowed = @(
        [Security.Principal.WindowsIdentity]::GetCurrent().User.Value,
        'S-1-5-18',       # SYSTEM
        'S-1-5-32-544',   # Local administrators
        'S-1-3-0'        # Creator owner
    )
    foreach ($rule in (Get-Acl -LiteralPath $Path).Access) {
        if ($rule.AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow) {
            $sid = $rule.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value
            if ($allowed -notcontains $sid) {
                throw "Folder access includes another account. Review privacy before proceeding."
            }
        }
    }
}
