import csv
import io
import json

import pytest
from fastapi.testclient import TestClient

from ai_company_eval import core, providers, web
from ai_company_eval.config import Settings
from ai_company_eval.models import PipelineRow, RowStatus
from ai_company_eval.portfolio import run_demo, summarize


@pytest.fixture
def client():
    with TestClient(web.create_app()) as client:
        yield client


def test_routes_and_packaged_assets_from_other_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with TestClient(web.create_app()) as client:
        assert client.get("/health").json() == {"status": "ok", "mode": "portfolio"}
        root = client.get("/")
        assert root.status_code == 200
        assert "AI Company Evaluation Pipeline" in root.text
        assert "readonly" in root.text
        for path in ("/static/app.css", "/static/app.js"):
            assert client.get(path).status_code == 200
        assert len(client.post("/api/demo/run").json()["rows"]) == 8
    assert list(tmp_path.iterdir()) == []  # No cache, upload or result persistence.


def test_deterministic_demo_contract_and_calculated_summary(client):
    first_response = client.post("/api/demo/run")
    assert first_response.status_code == 200
    first = first_response.json()
    second = client.post("/api/demo/run").json()
    assert first["rows"] == second["rows"]
    assert first["exports"] == second["exports"]
    rows = first["rows"]
    successes = [r for r in rows if r["status"] == "SUCCESS"]
    failures = [r for r in rows if r["status"] != "SUCCESS"]
    assert len(rows) == 8
    assert len(successes) == 7
    assert len(failures) == 1
    assert failures[0]["status"] == "CACHE_MISS"
    assert failures[0]["error"] == "no cached content"
    assert failures[0]["score"] is None
    assert failures[0]["validation_status"] == "Not evaluated"
    assert not failures[0]["cache_hit"]
    assert all(r["validation_status"] == "Validated" for r in successes)
    summary = first["summary"]
    assert summary["companies"] == len(rows)
    assert summary["successful"] == len(successes)
    assert summary["failed"] == len(failures)
    assert summary["average_score"] == round(sum(r["score"] for r in successes) / len(successes), 1)
    assert summary["cache_rate"] == 100 * sum(r["cache_hit"] for r in rows) / len(rows)
    assert summary["runtime_ms"] > 0
    first["summary"].pop("runtime_ms")
    second["summary"].pop("runtime_ms")
    assert first == second


def test_summary_uses_successful_scored_rows_only():
    rows = [PipelineRow(company_name="Test", website="https://example.test", project="p", status=RowStatus.SUCCESS, score=20),
            PipelineRow(company_name="Failed", website="https://example.test", project="p", status=RowStatus.EVALUATION_ERROR, score=90)]
    assert summarize(rows, 12).average_score == 20
    assert summarize([], 12).average_score is None
    assert summarize([], 12).cache_rate == 0


@pytest.mark.parametrize("live_flags", [False, True])
def test_portfolio_cannot_construct_or_use_live_components(monkeypatch, live_flags):
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append("forbidden")
        raise AssertionError("Portfolio tried a live component")

    monkeypatch.setattr(core.WebsiteFetcher, "__init__", forbidden)
    monkeypatch.setattr(core.WebsiteFetcher, "fetch", forbidden)
    for provider in (providers.OpenAIProvider, providers.AnthropicProvider):
        monkeypatch.setattr(provider, "__init__", forbidden)
        monkeypatch.setattr(provider, "evaluate", forbidden)
    # Even accidental live flags and credentials cannot select a live web execution path.
    monkeypatch.setenv("ALLOW_LIVE_FETCH", str(live_flags).lower())
    monkeypatch.setenv("ALLOW_LIVE_PROVIDERS", str(live_flags).lower())
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-sentinel")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-only-sentinel")
    with TestClient(web.create_app()) as client:
        assert client.post("/api/demo/run").json()["summary"]["successful"] == 7
        for provider in ("openai", "anthropic"):
            assert client.post("/api/demo/run", json={"provider": provider}).status_code == 400
            assert client.post(f"/api/demo/run?provider={provider}").status_code == 400
        assert client.post("/api/demo/run", json={"url": "https://example.test", "prompt": "override"}).status_code == 400
    assert attempts == []


def test_invalid_provider_output_remains_rejected(monkeypatch, client):
    monkeypatch.setattr(providers.MockProvider, "evaluate", lambda *args, **kwargs: {"score": 999, "recommendation": "invalid", "rationale": "invalid"})
    payload = client.post("/api/demo/run").json()
    assert [r["status"] for r in payload["rows"]].count("EVALUATION_ERROR") == 7
    assert payload["rows"][-1]["status"] == "CACHE_MISS"
    assert payload["summary"]["average_score"] is None
    assert payload["summary"]["successful"] == 0
    assert all(row["validation_status"] == "Rejected" for row in payload["rows"][:-1])


def test_exports_roundtrip_actual_rows_with_special_characters(monkeypatch):
    def special_output(*args, **kwargs):
        return {"score": 42, "recommendation": 'Review, "carefully"', "rationale": "Line one\nLine two — synthetic"}

    monkeypatch.setattr(providers.MockProvider, "evaluate", special_output)
    result = run_demo()
    rows = [row.model_dump(mode="json") for row in result.rows]
    assert json.loads(result.exports["json"]) == rows
    csv_rows = list(csv.DictReader(io.StringIO(result.exports["csv"])))
    assert len(csv_rows) == len(rows)
    for actual, expected in zip(csv_rows, rows, strict=True):
        assert actual == {key: "" if value is None else str(value) for key, value in expected.items()}


def test_portfolio_security_and_controlled_errors(client, monkeypatch, caplog):
    assert web.create_app().debug is False
    response = client.get("/", headers={"Origin": "https://example.test"})
    assert "access-control-allow-origin" not in response.headers
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert client.post("/api/demo/run", content=b"x" * 2048).status_code == 413
    assert client.post("/api/demo/run", content=iter([b"small", b"chunks"])).status_code == 400
    assert client.post("/api/upload").status_code == 404
    sentinel = "TEST_ONLY_PRIVATE_ERROR"

    def fail():
        raise RuntimeError(sentinel)

    monkeypatch.setattr(web, "run_demo", fail)
    response = client.post("/api/demo/run")
    assert response.status_code == 500
    assert response.json() == {"detail": "The demo could not complete. Please try again."}
    assert sentinel not in response.text + caplog.text
    assert "Traceback" not in response.text


def test_template_escapes_prompt(monkeypatch, client):
    monkeypatch.setattr(web, "prompt_preview", lambda: '</textarea><script>alert("test")</script>')
    response = client.get("/")
    assert '</textarea><script>alert' not in response.text
    assert "&lt;/textarea&gt;&lt;script&gt;" in response.text


def test_local_web_stays_an_offline_demo():
    with TestClient(web.create_app(Settings(mode="local", allow_live_fetch=True, allow_live_providers=True))) as client:
        assert client.get("/health").json()["mode"] == "local"
        assert client.post("/api/demo/run").json()["summary"]["successful"] == 7
        assert client.post("/api/demo/run", json={"provider": "openai"}).status_code == 400
