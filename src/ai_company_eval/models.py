from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl, field_validator


class CompanyRecord(BaseModel):
    company_name: str = Field(min_length=1)
    website: HttpUrl
    notes: str = ""

    @field_validator("company_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("company_name must not be blank")
        return value


class ScrapedContent(BaseModel):
    company_name: str
    website: str
    combined_text: str
    content_sha256: str


class EvaluationResult(BaseModel):
    score: int = Field(ge=0, le=100)
    recommendation: str = Field(min_length=1, max_length=1000)
    rationale: str = Field(min_length=1, max_length=2000)


class RowStatus(StrEnum):
    SUCCESS = "SUCCESS"
    SCRAPE_ERROR = "SCRAPE_ERROR"
    CACHE_MISS = "CACHE_MISS"
    EVALUATION_ERROR = "EVALUATION_ERROR"


class PipelineRow(BaseModel):
    company_name: str
    website: str
    project: str
    status: RowStatus
    score: int | None = None
    recommendation: str | None = None
    rationale: str | None = None
    cache_hit: bool = False
    error: str | None = None
