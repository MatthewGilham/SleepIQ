import subprocess


def test_credential_display_requires_explicit_owner_action() -> None:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-File", "scripts/view-ingest-credential.ps1"],
        capture_output=True, text=True, check=False, timeout=15,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert result.returncode != 0
    assert "explicit -Show" in result.stderr


def test_invalid_credential_rejected_before_ui_initialization() -> None:
    command = """
        . ./scripts/credential-dialog.ps1
        function Add-Type { throw 'UI initialization should not occur' }
        try { Show-IngestCredential 'synthetic-invalid'; exit 1 }
        catch {
            if ($_.Exception.Message -eq 'Stored ingest credential format is invalid.') { exit 0 }
            exit 2
        }
    """
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True, text=True, check=False, timeout=15,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "synthetic-invalid" not in result.stdout
