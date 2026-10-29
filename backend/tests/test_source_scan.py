import secrets
from pathlib import Path

import pytest
from detect_secrets.core.scan import scan_line
from detect_secrets.settings import default_settings
from scan_source import validate_candidate


@pytest.mark.parametrize(
    "name", [".env", ".env.local", "nested/KEY.pem", "x.sqlite3", "../outside.py"]
)
def test_private_or_escaping_candidate_rejected_before_reads(name: str) -> None:
    with pytest.raises(ValueError):
        validate_candidate(Path.cwd(), name)


def test_synthetic_credential_is_detected() -> None:
    # Generate synthetic input in memory, never a user's credential or a committed secret fixture.
    line = "password = " + repr(secrets.token_hex(24))
    with default_settings():
        assert list(scan_line(line))


def test_source_path_is_accepted() -> None:
    root = Path.cwd()
    assert validate_candidate(root, "backend/app/main.py") == root / "backend/app/main.py"
