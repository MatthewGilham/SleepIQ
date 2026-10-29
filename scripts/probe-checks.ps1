function Test-ProbeRequests([string]$Token) {
    if ($Token -cnotmatch '^[0-9a-f]{64}$') { throw 'Stored ingest credential is invalid.' }
    $auth = @{ Authorization = 'Bearer ' + $Token }
    $cases = @(
        @{ Label='HTTPS health'; Path='/health'; Method='GET'; Headers=@{}; Status=200; Json='health' },
        @{ Label='Authenticated synthetic POST'; Path='/transport-check'; Method='POST'; Headers=$auth; Status=200; Json='probe' },
        @{ Label='Missing credential rejected'; Path='/transport-check'; Method='POST'; Headers=@{}; Status=401 },
        @{ Label='Wrong credential rejected'; Path='/transport-check'; Method='POST'; Headers=@{Authorization='Bearer invalid'}; Status=401 },
        @{ Label='Browser origin rejected'; Path='/transport-check'; Method='POST'; Headers=@{Authorization=('Bearer ' + $Token); Origin='https://example.invalid'}; Status=403 },
        @{ Label='Dashboard absent'; Path='/'; Method='GET'; Headers=$auth; Status=404 },
        @{ Label='Dashboard API absent'; Path='/api/v1/status'; Method='GET'; Headers=$auth; Status=404 },
        @{ Label='API documentation absent'; Path='/docs'; Method='GET'; Headers=$auth; Status=404 },
        @{ Label='Real ingestion disabled'; Path='/api/ingest'; Method='POST'; Headers=$auth; Status=503 }
    )
    foreach ($case in $cases) {
        $request = @{
            Uri = ('https://sync.mgilham.online:8443' + $case.Path)
            Method = $case.Method
            Headers = $case.Headers
            UseBasicParsing = $true
            MaximumRedirection = 0
            TimeoutSec = 10
            ErrorAction = 'Stop'
        }
        if ($case.Method -eq 'POST') {
            $request.ContentType = 'application/json'
            $request.Body = '{"probe":"sleepiq"}'
        }
        $response = $null
        try {
            # Default Windows TLS validation remains enabled. Never follow credential redirects.
            $response = Invoke-WebRequest @request
            $status = [int]$response.StatusCode
        } catch {
            if ($_.Exception.Response) {
                $status = [int]$_.Exception.Response.StatusCode
            } else {
                throw ('FAIL: ' + $case.Label + '; connection/TLS failed. Raw error withheld.')
            }
        }
        if ($status -ne $case.Status) {
            throw ('FAIL: ' + $case.Label + '; expected HTTP ' + $case.Status + ', got ' + $status + '.')
        }
        if ($case.Json) {
            try { $payload = $response.Content | ConvertFrom-Json -ErrorAction Stop }
            catch { throw ('FAIL: ' + $case.Label + '; invalid JSON response.') }
            $names = @($payload.PSObject.Properties.Name | Sort-Object)
            if ($case.Json -eq 'health') {
                if (($names -join ',') -ne 'status' -or $payload.status -cne 'ok') {
                    throw 'FAIL: Unexpected health response.'
                }
            } elseif (($names -join ',') -ne 'status,stored' -or
                $payload.status -cne 'transport_ok' -or $payload.stored -isnot [bool] -or $payload.stored) {
                throw 'FAIL: Unexpected synthetic response; no stored-data acknowledgement expected.'
            }
        }
        Write-Output ('PASS: ' + $case.Label)
    }
}
