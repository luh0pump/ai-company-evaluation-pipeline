from __future__ import annotations

import hashlib
import json
import os

from .models import CompanyRecord, EvaluationResult, ScrapedContent


class MockProvider:
    def evaluate(self, *, company: CompanyRecord, content: ScrapedContent, prompt: str) -> EvaluationResult:
        corpus = f"{company.company_name} {company.notes} {content.combined_text}".lower()
        hits = sum(corpus.count(term) for term in ("automation", "software", "industrial", "b2b", "api", "data"))
        stable = hashlib.sha256(f"{company.company_name}|{prompt}|{content.content_sha256}".encode()).digest()[0] % 11
        score = min(100, 35 + hits * 8 + stable)
        recommendation = (
            "High-priority outreach with a concrete use case."
            if score >= 70
            else "Qualify manually before outreach."
            if score >= 50
            else "Low priority unless additional evidence appears."
        )
        return EvaluationResult(
            score=score,
            recommendation=recommendation,
            rationale="Deterministic mock output for zero-cost testing; not a real sales assessment.",
        )


class OpenAIProvider:
    def __init__(self, *, model: str, timeout_seconds: float = 30.0) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError('install with: pip install -e ".[openai]"') from exc
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        self.client = OpenAI(api_key=key, timeout=timeout_seconds)
        self.model = model

    def evaluate(self, *, company: CompanyRecord, content: ScrapedContent, prompt: str) -> EvaluationResult:
        schema = EvaluationResult.model_json_schema()
        user_text = (
            f"Company: {company.company_name}\nWebsite: {company.website}\nNotes: {company.notes}\n\n"
            f"Website text:\n{content.combined_text[:120000]}"
        )
        response = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": [{"type": "input_text", "text": prompt}]},
                {"role": "user", "content": [{"type": "input_text", "text": user_text}]},
            ],
            text={"format": {"type": "json_schema", "name": "company_evaluation", "schema": schema, "strict": True}},
        )
        return EvaluationResult.model_validate_json(response.output_text)


class AnthropicProvider:
    def __init__(self, *, model: str, timeout_seconds: float = 30.0) -> None:
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise RuntimeError('install with: pip install -e ".[anthropic]"') from exc
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        self.client = Anthropic(api_key=key, timeout=timeout_seconds)
        self.model = model

    def evaluate(self, *, company: CompanyRecord, content: ScrapedContent, prompt: str) -> EvaluationResult:
        schema = EvaluationResult.model_json_schema()
        message = (
            f"{prompt}\n\nReturn only JSON matching this schema:\n{json.dumps(schema)}\n\n"
            f"Company: {company.company_name}\nWebsite: {company.website}\nNotes: {company.notes}\n\n"
            f"Website text:\n{content.combined_text[:120000]}"
        )
        response = self.client.messages.create(
            model=self.model,
            max_tokens=800,
            temperature=0,
            messages=[{"role": "user", "content": message}],
        )
        text = "".join(block.text for block in response.content if getattr(block, "type", "") == "text").strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:].lstrip()
        return EvaluationResult.model_validate_json(text)


def build_provider(name: str, *, model: str):
    normalized = name.lower().strip()
    if normalized == "mock":
        return MockProvider()
    if normalized == "openai":
        return OpenAIProvider(model=model)
    if normalized == "anthropic":
        return AnthropicProvider(model=model)
    raise ValueError(f"unsupported provider: {name}")
