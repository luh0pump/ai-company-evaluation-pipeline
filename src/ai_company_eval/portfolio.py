"""Packaged, synthetic input passed through the existing pipeline, entirely in memory."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from time import perf_counter

from pydantic import BaseModel

from .core import RawContentStore, run_pipeline
from .models import CompanyRecord, PipelineRow, RowStatus, ScrapedContent
from .providers import MockProvider

ASSETS = Path(__file__).resolve().parent / "web_assets"
PROJECT = "company_evaluation"


class MemoryContentStore:
    def __init__(self) -> None:
        self.contents: dict[str, ScrapedContent] = {}

    def get(self, url: str) -> ScrapedContent | None:
        return self.contents.get(RawContentStore.key(url))

    def put(self, content: ScrapedContent) -> None:
        self.contents[RawContentStore.key(content.website)] = content


class DemoRow(PipelineRow):
    notes: str
    validation_status: str


class RunSummary(BaseModel):
    companies: int
    successful: int
    failed: int
    average_score: float | None
    cache_rate: float
    runtime_ms: float


class DemoResult(BaseModel):
    summary: RunSummary
    rows: list[DemoRow]
    metadata: dict[str, str]
    exports: dict[str, str]


def prompt_preview() -> str:
    return (ASSETS / "fixtures" / f"{PROJECT}.txt").read_text(encoding="utf-8").strip()


def summarize(rows: list[PipelineRow], runtime_ms: float) -> RunSummary:
    successful = sum(row.status == RowStatus.SUCCESS for row in rows)
    scores = [row.score for row in rows if row.status == RowStatus.SUCCESS and row.score is not None]
    return RunSummary(
        companies=len(rows), successful=successful, failed=len(rows) - successful,
        average_score=round(sum(scores) / len(scores), 1) if scores else None,
        cache_rate=round(100 * sum(row.cache_hit for row in rows) / len(rows), 1) if rows else 0,
        runtime_ms=runtime_ms,
    )


def export_rows(rows: list[DemoRow]) -> dict[str, str]:
    payload = [row.model_dump(mode="json") for row in rows]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(DemoRow.model_fields))
    writer.writeheader()
    writer.writerows(payload)
    return {"csv": output.getvalue(), "json": json.dumps(payload, indent=2, ensure_ascii=False)}


def run_demo() -> DemoResult:
    started = perf_counter()
    fixtures = json.loads((ASSETS / "fixtures" / "companies.json").read_text(encoding="utf-8"))
    companies = [CompanyRecord.model_validate(item["company"]) for item in fixtures]
    store = MemoryContentStore()
    for company, fixture in zip(companies, fixtures, strict=True):
        content = fixture.get("content")
        if content is not None:
            store.put(ScrapedContent(
                company_name=company.company_name, website=str(company.website),
                combined_text=content, content_sha256=hashlib.sha256(content.encode()).hexdigest(),
            ))
    results = run_pipeline(
        companies, project=PROJECT, prompt=prompt_preview(), provider=MockProvider(),
        store=store, fetcher=None,
    )
    rows = [DemoRow(
        **row.model_dump(), notes=company.notes,
        validation_status=("Validated" if row.status == RowStatus.SUCCESS else
                           "Rejected" if row.status == RowStatus.EVALUATION_ERROR else "Not evaluated"),
    ) for company, row in zip(companies, results, strict=True)]
    exports = export_rows(rows)
    elapsed = (perf_counter() - started) * 1000
    return DemoResult(
        summary=summarize(rows, elapsed), rows=rows, exports=exports,
        metadata={"dataset": "Synthetic demo data", "provider": "Demo / Deterministic", "project": PROJECT},
    )
