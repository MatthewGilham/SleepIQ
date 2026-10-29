"""Synthetic-only local chart preview; never opens the owner's data directory."""

import sys
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]
import uvicorn
from app.ai.config import AiConfig
from app.ai.provider import AiError, Completion
from app.ingest.store import import_bytes
from app.main import create_app

from backend.tests.factories import merge, new_store, night_blocks, payload


class PreviewProvider:
    """Canned stand-in: the preview never contacts an AI service. A question containing FAIL simulates a timeout."""

    def complete(self, system: str, user: str, max_output_tokens: int) -> Completion:
        if "FAIL" in user.rsplit("<<<", 1)[-1]:
            raise AiError(504, "timeout", "The AI service did not answer in time.")
        return Completion("SYNTHETIC preview answer. No AI service was contacted; this only shows the layout.", 1000, 20)


# A fixed isolated preview location allows presets to survive preview-server restarts.
# --fresh makes an independent test store; existing files are never removed/overwritten.
data = ROOT / ".cache" / "chart-preview" / (uuid4().hex if "--fresh" in sys.argv else "synthetic")
data.mkdir(parents=True, exist_ok=True)
if not (data / "sleepiq.sqlite3").exists():
    _, engine = new_store(data)
    groups = [
        night_blocks(
            date(2026, 7, 1) + timedelta(days=i),
            hr=50 + i % 11,
            hrv=None if i % 9 == 0 else 35 + i % 23,
            plan=[("Core", 120 + i % 40), ("Deep", 60), ("REM", 70), ("Awake", 10), ("Core", 140)],
        )
        for i in range(120)
        if i % 13 != 0
    ]
    import_bytes(engine, data, payload(merge(*groups)))
    engine.dispose()
app = create_app(ROOT / "frontend" / "dist", chart_data=data, chart_synthetic=True,
                 ai_config=AiConfig(True, "synthetic-preview-not-a-key"), ai_provider=PreviewProvider())
print("SYNTHETIC chart preview only: http://127.0.0.1:8766", flush=True)
uvicorn.run(app, host="127.0.0.1", port=8766, access_log=False)
