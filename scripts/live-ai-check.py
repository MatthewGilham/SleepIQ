"""One live AI validation request on SYNTHETIC data only (owner-run; the key never leaves your shell).

Usage (PowerShell, from the repository root):
    $env:SLEEPIQ_AI_ENABLED = "1"
    $env:SLEEPIQ_OPENAI_API_KEY = Read-Host "Key"   # typed into your own shell, not shown to the agent
    .venv\\Scripts\\python.exe scripts/live-ai-check.py --confirm-spend

Sends exactly one request through the real application path (budget, evidence, provider). It opens
no real health store, prints no key, and reports status, token counts and the synthetic answer.
"""

import os
import sys
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]
from app.ai.config import AiConfig
from app.ai.provider import OpenAIProvider
from app.ingest.store import import_bytes
from app.main import create_app
from fastapi.testclient import TestClient

from backend.tests.factories import merge, new_store, night_blocks, payload

if "--confirm-spend" not in sys.argv:
    sys.exit("Refusing to send: add --confirm-spend to approve one billable request with synthetic data.")
config = AiConfig.from_env(os.environ)
if config.state != "ready":
    sys.exit(f"AI state is '{config.state}'. Set SLEEPIQ_AI_ENABLED=1 and SLEEPIQ_OPENAI_API_KEY first.")

data = ROOT / ".cache" / "live-check" / uuid4().hex
data.mkdir(parents=True)
_, engine = new_store(data)
groups = [
    night_blocks(
        date(2026, 9, 1) + timedelta(days=i),
        hr=50 + i % 9,
        hrv=35 + (i * 7) % 23,
        plan=[("Core", 100 + 4 * i), ("Deep", 60), ("REM", 70), ("Awake", 10), ("Core", 140)],
    )
    for i in range(45)
]
import_bytes(engine, data, payload(merge(*groups)))
engine.dispose()

app = create_app(chart_data=data, chart_synthetic=True, ai_config=config, ai_provider=OpenAIProvider(config))
client = TestClient(app, base_url="http://localhost", client=("127.0.0.1", 50123))
headers = {"origin": "http://localhost", "x-sleepiq-request": "charts"}
body = {
    "question": "Is my sleep duration related to my overnight HRV in this range?",
    "metrics": ["asleep_s", "hrv_mean"],
    "range": "all",
    "confirm": True,
}
reply = client.post("/api/v1/analysis", json=body, headers=headers)
print("HTTP status:", reply.status_code)
result = reply.json()
if reply.status_code != 200:
    sys.exit(f"Failed safely: {result.get('detail')}")
print("model:", result["model"])
print("usage counter:", result["usage"])
print("evidence correlation:", result["evidence"]["correlations"])
print("answer:\n" + result["answer"])
print("key present in reply:", (config.api_key or "") in reply.text)
