import sys
from types import SimpleNamespace

import pytest

from ai_company_eval.config import Settings
from ai_company_eval.providers import AnthropicProvider, OpenAIProvider, build_provider


def test_secure_defaults_and_portfolio_flags(monkeypatch):
    assert Settings.from_env() == Settings()
    monkeypatch.setenv("ALLOW_LIVE_FETCH", "true")
    assert not Settings.from_env().live_fetch_enabled
    monkeypatch.setenv("APP_MODE", "local")
    assert Settings.from_env().live_fetch_enabled


@pytest.mark.parametrize("key,value", [("APP_MODE", "invalid"), ("ALLOW_LIVE_FETCH", "yes"), ("ALLOW_LIVE_PROVIDERS", "1")])
def test_invalid_configuration_fails_closed(monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError):
        Settings.from_env()


@pytest.mark.parametrize("name,constructor", [("openai", OpenAIProvider), ("anthropic", AnthropicProvider)])
def test_live_provider_requires_all_configuration(monkeypatch, name, constructor):
    prefix = name.upper()
    with pytest.raises(ValueError, match="APP_MODE=local"):
        constructor(model="explicit-model")
    monkeypatch.setenv("APP_MODE", "local")
    with pytest.raises(ValueError, match="ALLOW_LIVE_PROVIDERS"):
        build_provider(name)
    monkeypatch.setenv("ALLOW_LIVE_PROVIDERS", "true")
    with pytest.raises(ValueError, match=f"{prefix}_API_KEY"):
        build_provider(name)
    monkeypatch.setenv(f"{prefix}_API_KEY", "test-only-sentinel")
    with pytest.raises(ValueError, match=f"{prefix}_MODEL"):
        build_provider(name)


@pytest.mark.parametrize("name,sdk_class", [("openai", "OpenAI"), ("anthropic", "Anthropic")])
def test_model_from_provider_environment_or_explicit_config(monkeypatch, name, sdk_class):
    monkeypatch.setenv("APP_MODE", "local")
    monkeypatch.setenv("ALLOW_LIVE_PROVIDERS", "true")
    monkeypatch.setenv(f"{name.upper()}_API_KEY", "test-only-sentinel")
    monkeypatch.setenv(f"{name.upper()}_MODEL", "environment-model")
    monkeypatch.setitem(sys.modules, name, SimpleNamespace(**{sdk_class: lambda **kwargs: object()}))
    assert build_provider(name).model == "environment-model"
    assert build_provider(name, model="explicit-model").model == "explicit-model"


def test_unknown_provider_does_not_fall_back():
    with pytest.raises(ValueError, match="unsupported provider"):
        build_provider("typo")
