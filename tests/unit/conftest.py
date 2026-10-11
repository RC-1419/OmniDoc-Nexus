"""Unit tests must not see the stand-ins that the integration tests install on the shared `deps` module."""
import pytest

from omnidoc.api import deps
from tests.conftest import REAL_LLM_FOR


@pytest.fixture(autouse=True)
def _real_llm_for(monkeypatch):
    monkeypatch.setattr(deps, "llm_for", REAL_LLM_FOR)
