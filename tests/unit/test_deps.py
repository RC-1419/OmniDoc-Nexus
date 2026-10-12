from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from omnidoc.api import deps
from omnidoc.core.ratelimit import RateLimiter


def test_too_many_sets_status_and_retry_after():
    e = deps.too_many(42)
    assert e.status_code == 429 and e.headers["Retry-After"] == "42" and "42" in e.detail


def test_client_ip():
    assert deps.client_ip(SimpleNamespace(
        client=SimpleNamespace(host="1.2.3.4"))) == "1.2.3.4"
    assert deps.client_ip(SimpleNamespace(client=None)) == "unknown"


def test_enforce_allows_then_refuses(monkeypatch):
    monkeypatch.setattr(deps, "limiter", RateLimiter())
    deps.enforce("k", 2, 60)
    deps.enforce("k", 2, 60)
    with pytest.raises(HTTPException) as e:
        deps.enforce("k", 2, 60)
    assert e.value.status_code == 429 and int(
        e.value.headers["Retry-After"]) > 0


def test_current_user_needs_a_valid_token(monkeypatch):
    monkeypatch.setattr(deps, "decode_access_token", lambda token: None)
    db = SimpleNamespace(get=lambda model, pk: None)
    with pytest.raises(HTTPException) as e:
        deps.get_current_user("garbage", db)
    assert e.value.status_code == 401 and e.value.headers["WWW-Authenticate"] == "Bearer"


def test_current_user_rejects_a_token_for_a_deleted_user(monkeypatch):
    monkeypatch.setattr(deps, "decode_access_token", lambda token: 5)
    db = SimpleNamespace(get=lambda model, pk: None)
    with pytest.raises(HTTPException) as e:
        deps.get_current_user("t", db)
    assert e.value.status_code == 401


def test_current_user_returns_the_user(monkeypatch):
    user = object()
    monkeypatch.setattr(deps, "decode_access_token", lambda token: 5)
    assert deps.get_current_user("t", SimpleNamespace(
        get=lambda model, pk: user if pk == 5 else None)) is user


def patch_providers(monkeypatch, configured, default="mistral"):
    monkeypatch.setattr(deps, "configured_providers", lambda: configured)
    monkeypatch.setattr(deps, "get_settings",
                        lambda: SimpleNamespace(default_llm=default))
    monkeypatch.setattr(deps, "get_llm_for_user_choice",
                        lambda choice: f"llm:{choice}")


def test_llm_for_without_any_provider_is_503(monkeypatch):
    patch_providers(monkeypatch, [])
    with pytest.raises(HTTPException) as e:
        deps.llm_for(None)
    assert e.value.status_code == 503


def test_llm_for_refuses_a_provider_that_is_not_configured(monkeypatch):
    patch_providers(monkeypatch, ["groq"])
    with pytest.raises(HTTPException) as e:
        deps.llm_for("openai")
    assert e.value.status_code == 400


def test_llm_for_normalises_the_choice(monkeypatch):
    patch_providers(monkeypatch, ["groq", "mistral"])
    assert deps.llm_for("  GROQ ") == "llm:groq"


def test_llm_for_default_falls_back_to_the_first_configured(monkeypatch):
    patch_providers(monkeypatch, ["groq", "mistral"], default="mistral")
    assert deps.llm_for(None) == "llm:mistral"
    patch_providers(monkeypatch, ["groq"], default="mistral")
    assert deps.llm_for(None) == "llm:groq"
