import subprocess

import pytest


@pytest.mark.parametrize("failure", ["none", "authentication", "stored", "redirect"])
def test_live_verifier_rejects_unsafe_responses(failure: str) -> None:
    # Exercise the checker with a synthetic HTTP boundary, never real credentials or networking.
    command = r'''
        . ./scripts/probe-checks.ps1
        function Invoke-WebRequest {
            param($Uri, $Method, $Headers, $UseBasicParsing, $MaximumRedirection,
                  $TimeoutSec, $ErrorAction, $ContentType, $Body)
            if ($MaximumRedirection -ne 0) { throw 'Redirect guard absent' }
            $status = 200
            $content = '{}'
            $path = ([uri]$Uri).AbsolutePath
            if ($path -eq '/health') { $content = '{"status":"ok"}' }
            elseif ($path -eq '/transport-check') {
                if ($Headers.Origin) { $status = 403 }
                elseif ($Headers.Authorization -ne ('Bearer ' + ('a' * 64))) {
                    $status = 401
                    if ('FAILURE' -eq 'authentication') { $status = 200 }
                } else {
                    $content = '{"status":"transport_ok","stored":false}'
                    if ('FAILURE' -eq 'stored') {
                        $content = '{"status":"transport_ok","stored":true}'
                    }
                    if ('FAILURE' -eq 'redirect') { $status = 302 }
                }
            }
            elseif ($path -eq '/api/ingest') { $status = 503 }
            else { $status = 404 }
            return [pscustomobject]@{ StatusCode=$status; Content=$content }
        }
        try { Test-ProbeRequests ('a' * 64); exit 0 }
        catch { Write-Output 'Verification rejected'; exit 1 }
    '''.replace("FAILURE", failure)
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True, text=True, check=False, timeout=15,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert result.returncode == (0 if failure == "none" else 1), result.stdout + result.stderr
    assert "a" * 64 not in result.stdout + result.stderr
