import os
import subprocess
from pathlib import Path


def test_wrong_archive_rejected_before_extraction(scratch: Path) -> None:
    archive = scratch / "synthetic.zip"
    archive.write_bytes(b"synthetic untrusted archive; never executable")
    environment = {**os.environ, "SLEEPIQ_TEST_ARCHIVE": str(archive)}
    command = (
        ". ./scripts/lego-tools.ps1; "
        "try { Assert-LegoArchive $env:SLEEPIQ_TEST_ARCHIVE; exit 1 } "
        "catch { if ($_.Exception.Message -like 'Lego archive checksum mismatch*') "
        "{ Write-Output 'Rejected'; exit 0 }; throw }"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        cwd=Path(__file__).resolve().parents[3],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert result.returncode == 0, result.stderr
    assert "Rejected" in result.stdout
