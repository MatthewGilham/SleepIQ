"""Certificate expiry reporting and the PowerShell renewal decision helpers (synthetic certificates only)."""

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from app import certstatus
from app.main import create_app
from fastapi.testclient import TestClient

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[3]


def status_file(tmp_path: Path, expires: datetime, result: str = "none") -> Path:
    path = tmp_path / "certificate-status.json"
    path.write_text(
        json.dumps({"not_after_utc": expires.strftime("%Y-%m-%dT%H:%M:%SZ"), "last_result": result}),
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    ("days", "state"), [(90, "ok"), (31, "ok"), (30, "due"), (15, "due"), (14, "urgent"), (0, "urgent")]
)
def test_state_thresholds(tmp_path, days, state):
    # A few minutes of slack keeps "N whole days left" exact.
    result = certstatus.read(status_file(tmp_path, NOW + timedelta(days=days, minutes=5)), NOW)
    assert (result["state"], result["days_left"]) == (state, days)


def test_expired_and_unknown_are_never_healthy(tmp_path):
    expired = certstatus.read(status_file(tmp_path, NOW - timedelta(hours=1)), NOW)
    assert expired["state"] == "expired" and expired["days_left"] == -1
    assert certstatus.read(tmp_path / "missing.json", NOW)["state"] == "unknown"
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert certstatus.read(bad, NOW)["state"] == "unknown"
    bad.write_text(json.dumps({"not_after_utc": "tomorrow-ish"}), encoding="utf-8")
    assert certstatus.read(bad, NOW)["state"] == "unknown"


def test_unrecognised_result_text_is_not_echoed(tmp_path):
    path = status_file(tmp_path, NOW + timedelta(days=60), result="SECRET-looking free text")
    assert certstatus.read(path, NOW)["last_result"] == "none"


def test_status_endpoint_includes_certificate_only_when_configured(tmp_path):
    path = status_file(tmp_path, datetime.now(UTC) + timedelta(days=60), "renewed")
    with TestClient(create_app(certificate_status=path), base_url="http://localhost") as client:
        body = client.get("/api/v1/status").json()
    assert body["certificate"]["state"] == "ok" and body["certificate"]["last_result"] == "renewed"
    assert set(body["certificate"]) == {"state", "days_left", "expires", "last_result"}
    with TestClient(create_app(), base_url="http://localhost") as client:
        assert "certificate" not in client.get("/api/v1/status").json()


def powershell(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["powershell", "-NoProfile", "-Command", ". ./scripts/certificate-tools.ps1; " + command],
        cwd=ROOT, capture_output=True, text=True, check=False, timeout=60,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def test_renewal_due_decision():
    run = powershell(
        "$n=[datetime]'2026-11-01'; "
        "Write-Output (Test-RenewalDue ([datetime]'2026-12-01') $n 30); "  # exactly 30 days -> due
        "Write-Output (Test-RenewalDue ([datetime]'2026-12-02') $n 30); "  # 31 days -> not due
        "Write-Output (Test-RenewalDue ([datetime]'2026-10-31') $n 30)"  # already expired -> due
    )
    assert run.stdout.split() == ["True", "False", "True"], run.stderr


def test_status_file_written_from_a_synthetic_certificate(tmp_path):
    folder = tmp_path.as_posix()
    run = powershell(
        "$k=[Security.Cryptography.RSA]::Create(2048); "
        "$r=New-Object Security.Cryptography.X509Certificates.CertificateRequest('CN=sync.mgilham.online',$k,"
        "[Security.Cryptography.HashAlgorithmName]::SHA256,[Security.Cryptography.RSASignaturePadding]::Pkcs1); "
        "$c=$r.CreateSelfSigned([DateTimeOffset]::UtcNow.AddDays(-1),[DateTimeOffset]::UtcNow.AddDays(40)); "
        f"$p='{folder}/synthetic.crt'; "
        "[IO.File]::WriteAllBytes($p,$c.Export('Cert')); "
        f"Write-CertificateStatus '{folder}' $p 'renewed' ([DateTime]::UtcNow); "
        f"Write-CertificateStatus '{folder}' $p"  # a plain refresh keeps the earlier result
    )
    assert run.returncode == 0, run.stderr
    written = json.loads((tmp_path / "certificate-status.json").read_text(encoding="utf-8"))
    assert set(written) == {"hostname", "not_after_utc", "checked_utc", "last_result", "last_attempt_utc"}
    assert written["hostname"] == "sync.mgilham.online" and written["last_result"] == "renewed"
    assert certstatus.read(tmp_path / "certificate-status.json")["state"] == "ok"
    assert not list(tmp_path.glob("*.tmp"))


def test_scripts_parse_cleanly():
    for name in ("renew-certificate.ps1", "renewal-task.ps1", "certificate-tools.ps1", "start.ps1"):
        run = powershell(
            "$e=$null; [void][Management.Automation.Language.Parser]::ParseFile("
            f"'{(ROOT / 'scripts' / name).as_posix()}',[ref]$null,[ref]$e); "
            "if ($e) { $e | ForEach-Object { $_.Message }; exit 1 }"
        )
        assert run.returncode == 0, (name, run.stdout)
