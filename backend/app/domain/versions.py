"""One validated active measurement/score pair; absent setting preserves legacy behaviour."""

import json
from dataclasses import asdict, dataclass

from sqlalchemy import Connection, text

from app.db.migrate import WEIGHTED_HR_REVISION
from app.domain.config import (
    DERIVE,
    SCORE,
    WEIGHTED_DERIVE,
    WEIGHTED_SCORE,
    DeriveConfig,
    ScoreConfig,
)

ACTIVE_KEY = "derivation.active.v1"


@dataclass(frozen=True)
class ActivePair:
    derive: str = DERIVE.version
    score: str = SCORE.version
    policy_hash: str = DERIVE.config_hash()
    generation: int = 0

    @property
    def versions(self) -> list[str]:
        return [self.derive, self.score]

    @property
    def derive_config(self) -> DeriveConfig:
        return WEIGHTED_DERIVE if self.derive == WEIGHTED_DERIVE.version else DERIVE

    @property
    def score_config(self) -> ScoreConfig:
        return WEIGHTED_SCORE if self.score == WEIGHTED_SCORE.version else SCORE


def active_pair(conn: Connection) -> ActivePair:
    raw = conn.scalar(text("SELECT value_json FROM app_settings WHERE key=:k"), {"k": ACTIVE_KEY})
    if raw is None:
        return ActivePair()
    try:
        record = json.loads(raw)
        if not isinstance(record, dict) or set(record) != {
            "derive",
            "score",
            "policy_hash",
            "generation",
        }:
            raise ValueError
        pair = ActivePair(**record)
        if type(pair.generation) is not int or pair.generation < 1:
            raise ValueError
        if pair.versions not in [
            [DERIVE.version, SCORE.version],
            [WEIGHTED_DERIVE.version, WEIGHTED_SCORE.version],
        ]:
            raise ValueError
        if pair.policy_hash != pair.derive_config.config_hash():
            raise ValueError
        if (
            pair.derive == WEIGHTED_DERIVE.version
            and conn.scalar(text("SELECT version_num FROM alembic_version")) != WEIGHTED_HR_REVISION
        ):
            raise ValueError
        return pair
    except (TypeError, ValueError):
        raise ValueError("Invalid active calculation record; owner review required") from None


def ensure_current(conn: Connection, expected: ActivePair) -> None:
    if active_pair(conn) != expected:
        raise ValueError("Calculation version changed; restart this process")


def set_active(conn: Connection, weighted: bool) -> ActivePair:
    previous = active_pair(conn)
    derive, score = (WEIGHTED_DERIVE, WEIGHTED_SCORE) if weighted else (DERIVE, SCORE)
    pair = ActivePair(derive.version, score.version, derive.config_hash(), previous.generation + 1)
    conn.execute(
        text(
            "INSERT INTO app_settings(key,value_json) VALUES(:k,:v) "
            "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json"
        ),
        {"k": ACTIVE_KEY, "v": json.dumps(asdict(pair), sort_keys=True)},
    )
    return pair
