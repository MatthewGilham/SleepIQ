function Get-ProbeNetwork {
    $addresses = @(Get-NetIPAddress -AddressFamily IPv4 -IPAddress '192.168.1.190' -ErrorAction Stop)
    if ($addresses.Count -ne 1 -or $addresses[0].PrefixLength -ne 24) {
        throw 'Expected home IPv4 address/subnet changed; review DNS and network before continuing.'
    }
    $profiles = @(Get-NetConnectionProfile -InterfaceIndex $addresses[0].InterfaceIndex -ErrorAction Stop)
    if ($profiles.Count -ne 1 -or $profiles[0].NetworkCategory -ne 'Private') {
        throw 'Only the approved Private home connection is supported.'
    }
    $answers = @(Resolve-DnsName 'sync.mgilham.online' -Type A -DnsOnly -ErrorAction Stop |
        Where-Object { $_.Type -eq 'A' })
    if ($answers.Count -ne 1 -or $answers[0].IPAddress -ne '192.168.1.190') {
        throw 'DNS no longer matches the approved home IPv4 address.'
    }
    return $addresses[0].InterfaceAlias
}
