"""AI settings. Off unless explicitly enabled; the key comes only from the environment (P23)."""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

DEFAULT_MODEL = "gpt-6-luna"  # P23: economical starting model; configurable, never hard-wired
MODEL_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")


@dataclass(frozen=True)
class Limits:
    """P23 owner-approved local ceilings, enforced before any request leaves the PC."""

    input_tokens: int = 15_000
    output_tokens: int = 2_000
    per_day: int = 20
    per_month: int = 300
    max_metrics: int = 6
    max_nights: int = 90


LIMITS = Limits()


@dataclass(frozen=True)
class AiConfig:
    enabled: bool = False
    api_key: str | None = field(default=None, repr=False)
    model: str = DEFAULT_MODEL

    @property
    def state(self) -> str:
        if not self.enabled:
            return "disabled"
        return "ready" if self.api_key else "not_configured"

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> "AiConfig":
        model = environ.get("SLEEPIQ_AI_MODEL", DEFAULT_MODEL)
        if not MODEL_PATTERN.fullmatch(model):
            raise ValueError("SLEEPIQ_AI_MODEL contains unsupported characters")
        key = environ.get("SLEEPIQ_OPENAI_API_KEY", "").strip() or None
        return cls(environ.get("SLEEPIQ_AI_ENABLED") == "1", key, model)
