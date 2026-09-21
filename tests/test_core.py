from pathlib import Path

from ai_company_eval.core import RawContentStore, load_companies, load_prompt, run_pipeline
from ai_company_eval.models import CompanyRecord, EvaluationResult, RowStatus, ScrapedContent
from ai_company_eval.providers import MockProvider


def test_csv_input(tmp_path: Path):
    path = tmp_path / "companies.csv"
    path.write_text("company_name,website,notes\nAlpha,https://example.com,test\n", encoding="utf-8")
    rows = load_companies(path)
    assert rows[0].company_name == "Alpha"


def test_prompt_name_is_safe(tmp_path: Path):
    (tmp_path / "client_a.txt").write_text("Evaluate conservatively.", encoding="utf-8")
    assert load_prompt("client_a", tmp_path) == "Evaluate conservatively."


def test_cache_roundtrip(tmp_path: Path):
    store = RawContentStore(tmp_path)
    content = ScrapedContent(
        company_name="Alpha",
        website="https://example.com/",
        combined_text="hello",
        content_sha256="abc",
    )
    store.put(content)
    assert store.get("https://example.com/").combined_text == "hello"


def test_mock_is_deterministic():
    company = CompanyRecord(company_name="Alpha", website="https://example.com", notes="automation")
    content = ScrapedContent(
        company_name="Alpha",
        website=str(company.website),
        combined_text="B2B software automation",
        content_sha256="stable",
    )
    provider = MockProvider()
    a = provider.evaluate(company=company, content=content, prompt="prompt")
    b = provider.evaluate(company=company, content=content, prompt="prompt")
    assert a == b


def test_row_failure_isolated(tmp_path: Path):
    companies = [
        CompanyRecord(company_name="Alpha", website="https://example.com", notes=""),
        CompanyRecord(company_name="Beta", website="https://example.org", notes=""),
    ]
    store = RawContentStore(tmp_path)
    store.put(ScrapedContent(
        company_name="Alpha",
        website=str(companies[0].website),
        combined_text="software automation",
        content_sha256="a",
    ))

    rows = run_pipeline(
        companies,
        project="p",
        prompt="prompt",
        provider=MockProvider(),
        store=store,
    )

    assert rows[0].status == RowStatus.SUCCESS
    assert rows[1].status == RowStatus.CACHE_MISS


class InvalidProvider:
    def evaluate(self, **kwargs):
        return {"score": 999, "recommendation": "bad", "rationale": "bad"}


def test_invalid_structured_output_is_rejected(tmp_path: Path):
    company = CompanyRecord(company_name="Alpha", website="https://example.com", notes="")
    store = RawContentStore(tmp_path)
    store.put(ScrapedContent(
        company_name="Alpha",
        website=str(company.website),
        combined_text="software",
        content_sha256="a",
    ))

    rows = run_pipeline(
        [company],
        project="p",
        prompt="prompt",
        provider=InvalidProvider(),
        store=store,
    )

    assert rows[0].status == RowStatus.EVALUATION_ERROR
    assert rows[0].score is None


def test_exception_details_are_not_persisted(tmp_path):
    company = CompanyRecord(company_name="Test", website="https://example.test")
    sentinel = "TEST_ONLY_PRIVATE_ERROR"

    class FailingAdapter:
        def evaluate(self, **kwargs):
            raise RuntimeError(sentinel)

        def fetch(self, company):
            raise RuntimeError(sentinel)

    store = RawContentStore(tmp_path)
    arguments = dict(project="p", prompt="prompt", provider=FailingAdapter(), store=store, fetcher=FailingAdapter())
    failed_fetch = run_pipeline([company], **arguments)[0]
    assert failed_fetch.status == RowStatus.SCRAPE_ERROR
    assert sentinel not in failed_fetch.model_dump_json()
    store.put(ScrapedContent(company_name="Test", website=str(company.website), combined_text="fixture", content_sha256="fixture"))
    failed_provider = run_pipeline([company], **arguments)[0]
    assert failed_provider.status == RowStatus.EVALUATION_ERROR
    assert sentinel not in failed_provider.model_dump_json()
