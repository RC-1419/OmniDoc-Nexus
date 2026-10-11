"""Shared pytest setup.

Run everything:        python -m pytest
Only the fast ones:    python -m pytest -m unit
Only the database ones: python -m pytest -m integration

Integration tests use the database in DATABASE_URL (the same one scripts/try_api.py uses), create users named
test_<name>_<random> and delete them afterwards. Uploaded files go to a temporary vault folder that is removed
at the end, unless VAULT_DIR is already set (as it is in CI).
"""
import os
import shutil
import tempfile

import pytest

_TEMP_VAULT = None
if not os.environ.get("VAULT_DIR"):
    _TEMP_VAULT = tempfile.mkdtemp(prefix="omnidoc-test-vault-")
    # must happen before omnidoc reads its settings
    os.environ["VAULT_DIR"] = _TEMP_VAULT

from omnidoc.api import deps  # noqa: E402  (after VAULT_DIR is set)

# The integration tests swap deps.llm_for for a stand-in and keep it until the whole run ends. Remember the real one now,
# before that happens, so unit tests can put it back for themselves (see tests/unit/conftest.py).
REAL_LLM_FOR = deps.llm_for


def pytest_sessionfinish(session, exitstatus):
    if _TEMP_VAULT:
        shutil.rmtree(_TEMP_VAULT, ignore_errors=True)


def pytest_collection_modifyitems(items):
    for item in items:
        path = item.nodeid.replace("\\", "/")
        if "/integration/" in path or path.startswith("tests/integration"):
            item.add_marker(pytest.mark.integration)
        else:
            item.add_marker(pytest.mark.unit)
