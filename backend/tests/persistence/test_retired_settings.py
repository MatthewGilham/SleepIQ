"""P28: the AI assistant is gone; its usage counter is removed at start-up and no AI route exists."""

from pathlib import Path

from app.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.tests.factories import new_store

PRESET = '{"name":"keep me","v":1}'


def _rows(engine) -> dict[str, str]:
    with engine.connect() as conn:
        return dict(conn.execute(text("SELECT key,value_json FROM app_settings")).all())


def _seed(engine, usage: bool) -> None:
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_settings(key,value_json) VALUES('chart.preset.x',:v)"), {"v": PRESET})
        if usage:
            conn.execute(text("INSERT INTO app_settings(key,value_json) VALUES('ai.usage.v1',:v)"), {"v": '{"n": 3}'})


def test_usage_row_removed_once_and_preset_untouched(scratch: Path):
    data, engine = new_store(scratch)
    _seed(engine, usage=True)
    create_app(chart_data=data)
    assert _rows(engine) == {"chart.preset.x": PRESET}
    create_app(chart_data=data)
    assert _rows(engine) == {"chart.preset.x": PRESET}


def test_store_without_usage_row_unchanged(scratch: Path):
    data, engine = new_store(scratch)
    _seed(engine, usage=False)
    before = _rows(engine)
    create_app(chart_data=data)
    assert _rows(engine) == before


def test_no_analysis_routes_even_with_ai_env(scratch: Path, monkeypatch):
    monkeypatch.setenv("SLEEPIQ_AI_ENABLED", "1")
    monkeypatch.setenv("SLEEPIQ_OPENAI_API_KEY", "sk-fake-not-a-key")
    data, _ = new_store(scratch)
    app = create_app(chart_data=data)
    assert not [r for r in app.routes if getattr(r, "path", "").startswith("/api/v1/analysis")]
    client = TestClient(app, base_url="http://localhost", client=("127.0.0.1", 1))
    headers = {"origin": "http://localhost", "x-sleepiq-request": "charts"}
    assert client.get("/api/v1/analysis/status").status_code == 404
    assert client.post("/api/v1/analysis", json={}, headers=headers).status_code == 404
