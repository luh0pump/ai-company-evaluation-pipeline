from __future__ import annotations

import hashlib
from pathlib import Path

import typer

from .core import RawContentStore, WebsiteFetcher, load_companies, load_prompt, run_pipeline, write_results
from .models import ScrapedContent
from .providers import build_provider


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
    model: str = typer.Option("gpt-5.6-luna"),
    prompt_dir: Path = typer.Option(Path("prompts")),
    raw_dir: Path = typer.Option(Path("data/raw")),
    output_dir: Path = typer.Option(Path("out")),
) -> None:
    companies = load_companies(input)
    prompt = load_prompt(project, prompt_dir)
    rows = run_pipeline(
        companies,
        project=project,
        prompt=prompt,
        provider=build_provider(provider, model=model),
        store=RawContentStore(raw_dir),
        fetcher=WebsiteFetcher(),
    )
    csv_path, json_path = write_results(rows, output_dir, project)
    successes = sum(row.status == "SUCCESS" for row in rows)
    typer.echo(f"run complete: {successes}/{len(rows)} successful | {csv_path} | {json_path}")


if __name__ == "__main__":
    app()
