"""Start-up removal of settings rows retired by owner decision."""

from sqlalchemy import Engine, text

RETIRED_KEYS = ("ai.usage.v1",)  # local AI usage counter (counts only); the AI assistant was removed in P28


def remove_retired_settings(engine: Engine) -> None:
    with engine.begin() as conn:
        for key in RETIRED_KEYS:
            conn.execute(text("DELETE FROM app_settings WHERE key=:k"), {"k": key})
