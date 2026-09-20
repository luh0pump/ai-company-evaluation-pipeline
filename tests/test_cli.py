from pathlib import Path

from typer.testing import CliRunner

from ai_company_eval.cli import app


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
