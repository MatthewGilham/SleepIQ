"""Explicit migrations; never invoked on importing or starting the browser app."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine

LEGACY_HEALTH_REVISION = "0002_health"
WEIGHTED_HR_REVISION = "0003_weighted_hr"
SUPPORTED_HEALTH_REVISIONS = frozenset((LEGACY_HEALTH_REVISION, WEIGHTED_HR_REVISION))


def upgrade(engine: Engine) -> None:
    config = Config()
    scripts = Path(__file__).resolve().parent / "migrations"
    config.set_main_option("script_location", str(scripts).replace("%", "%%"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
