from __future__ import annotations

import hashlib
from pathlib import Path

import typer

from .core import RawContentStore, WebsiteFetcher, load_companies, load_prompt, run_pipeline, write_results
from .models import ScrapedContent
from .providers import build_provider
from .config import Settings


app = typer.Typer(no_args_is_help=True, help="Reusable website extraction + structured LLM evaluation pipeline.")


@app.command()
def demo(
    input: Path = typer.Option(Path("examples/companies.csv"), exists=True),
    project: str = typer.Option("company_evaluation"),
    prompt_dir: Path = typer.Option(Path("prompts")),
    output_dir: Path = typer.Option(Path("out")),
) -> None:
    companies = load_companies(input)
    prompt = load_prompt(project, prompt_dir)
    store = RawContentStore(output_dir / ".demo_cache")

    for company in companies:
        text = f"Synthetic portfolio fixture for {company.company_name}. Notes: {company.notes}."
        store.put(ScrapedContent(
            company_name=company.company_name,
            website=str(company.website),
            combined_text=text,
            content_sha256=hashlib.sha256(text.encode()).hexdigest(),
        ))

    rows = run_pipeline(
        companies,
        project=project,
        prompt=prompt,
        provider=build_provider("mock", model="mock"),
        store=store,
    )
    csv_path, json_path = write_results(rows, output_dir, project)
    typer.echo(f"offline demo complete: {csv_path} | {json_path}")


@app.command()
def run(
    input: Path = typer.Option(..., exists=True),
    project: str = typer.Option(...),
    provider: str = typer.Option("mock"),
    model: str | None = typer.Option(None, help="Live model; otherwise OPENAI_MODEL / ANTHROPIC_MODEL."),
    prompt_dir: Path = typer.Option(Path("prompts")),
    raw_dir: Path = typer.Option(Path("data/raw")),
    output_dir: Path = typer.Option(Path("out")),
) -> None:
    try:
        settings = Settings.from_env()
        if settings.mode != "local":
            raise ValueError("company-eval run requires APP_MODE=local; use company-eval demo for offline fixtures")
        selected_provider = build_provider(provider, model=model)
    except (ValueError, RuntimeError) as exc:
        raise typer.BadParameter(str(exc)) from None
    companies = load_companies(input)
    prompt = load_prompt(project, prompt_dir)
    rows = run_pipeline(
        companies,
        project=project,
        prompt=prompt,
        provider=selected_provider,
        store=RawContentStore(raw_dir),
        fetcher=WebsiteFetcher() if settings.live_fetch_enabled else None,
    )
    csv_path, json_path = write_results(rows, output_dir, project)
    successes = sum(row.status == "SUCCESS" for row in rows)
    typer.echo(f"run complete: {successes}/{len(rows)} successful | {csv_path} | {json_path}")


@app.command()
def web(
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(8000, min=1, max=65535),
) -> None:
    """Start the packaged web demo (install the web extra first)."""
    try:
        import uvicorn
        from .web import create_app
    except ImportError:
        typer.echo('Web dependencies missing. Install with: pip install -e ".[web]"', err=True)
        raise typer.Exit(1) from None
    try:
        application = create_app()
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from None
    uvicorn.run(application, host=host, port=port, log_level="warning", access_log=False)


if __name__ == "__main__":
    app()
