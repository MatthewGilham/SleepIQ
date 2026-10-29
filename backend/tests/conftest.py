"""Synthetic scratch data kept under the ignored workspace cache."""

from pathlib import Path
from uuid import uuid4

import pytest


@pytest.fixture
def scratch() -> Path:
    # Avoid restricted system-temp ACLs. Test artifacts are retained for inspection.
    path = Path(__file__).resolve().parents[2] / ".cache/test-runs" / uuid4().hex
    path.mkdir(parents=True)
    return path
