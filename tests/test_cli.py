from pathlib import Path
import json
import builtins

from typer.testing import CliRunner

from ai_company_eval.cli import app
from ai_company_eval import cli
from ai_company_eval.models import ScrapedContent


def test_offline_demo(tmp_path: Path):
    runner = CliRunner()
    repo_root = Path(__file__).resolve().parents[1]

    args = [
        "demo",
        "--input", str(repo_root / "examples" / "companies.csv"),
        "--project", "company_evaluation",
        "--prompt-dir", str(repo_root / "prompts"),
        "--output-dir", str(tmp_path),
    ]

    first = runner.invoke(app, args)
    assert first.exit_code == 0, first.output

    result = tmp_path / "company_evaluation_results.json"
    assert result.exists()
    content_a = result.read_text(encoding="utf-8")

    second = runner.invoke(app, args)
    assert second.exit_code == 0, second.output
    content_b = result.read_text(encoding="utf-8")

    assert content_a == content_b
    assert '"status": "SUCCESS"' in content_a


def test_run_requires_local_mode(tmp_path):
    path = tmp_path / "input.csv"
    path.write_text("company_name,website,notes\nTest,https://example.test,fixture\n")
    result = CliRunner().invoke(app, ["run", "--input", str(path), "--project", "p"])
    assert result.exit_code != 0
    assert "APP_MODE=local" in result.output


def test_local_cli_run_fetch_is_opt_in_and_cache_is_reused(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_MODE", "local")
    source = tmp_path / "input.csv"
    source.write_text("company_name,website,notes\nTest,https://example.test,fixture\n")
    (tmp_path / "p.txt").write_text("Evaluate conservatively.")
    args = ["run", "--input", str(source), "--project", "p", "--prompt-dir", str(tmp_path),
            "--raw-dir", str(tmp_path / "raw"), "--output-dir", str(tmp_path / "out")]
    fetches = []

    class FakeFetcher:
        def fetch(self, company):
            fetches.append(company.company_name)
            return ScrapedContent(company_name=company.company_name, website=str(company.website), combined_text="fixture software", content_sha256="synthetic")

    monkeypatch.setattr(cli, "WebsiteFetcher", FakeFetcher)
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    result_path = tmp_path / "out" / "p_results.json"
    assert json.loads(result_path.read_text())[0]["status"] == "CACHE_MISS"
    assert fetches == []
    monkeypatch.setenv("ALLOW_LIVE_FETCH", "true")
    for _ in range(2):
        result = CliRunner().invoke(app, args)
        assert result.exit_code == 0, result.output
    assert fetches == ["Test"]
    row = json.loads(result_path.read_text())[0]
    assert row["status"] == "SUCCESS"
    assert row["cache_hit"] is True


def test_requested_live_provider_never_falls_back(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_MODE", "local")
    source = tmp_path / "input.csv"
    source.write_text("company_name,website,notes\nTest,https://example.test,fixture\n")
    for name in ("openai", "anthropic"):
        result = CliRunner().invoke(app, ["run", "--input", str(source), "--project", "p", "--provider", name])
        assert result.exit_code != 0
        assert "ALLOW_LIVE_PROVIDERS" in result.output


def test_web_command_defaults_to_loopback(monkeypatch):
    import uvicorn

    calls = []
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: calls.append(kwargs))
    result = CliRunner().invoke(app, ["web"])
    assert result.exit_code == 0, result.output
    assert calls[0]["host"] == "127.0.0.1"
    assert calls[0]["port"] == 8000
    assert calls[0]["access_log"] is False


def test_web_missing_dependencies_has_install_instruction(monkeypatch):
    original_import = builtins.__import__

    def missing(name, *args, **kwargs):
        if name == "uvicorn":
            raise ImportError("test-only missing dependency")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing)
    result = CliRunner().invoke(app, ["web"])
    assert result.exit_code == 1
    assert 'pip install -e ".[web]"' in result.output
