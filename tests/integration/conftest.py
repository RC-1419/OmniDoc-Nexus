"""Fixtures for the tests that run the real API against the real database.

Stand-ins are used only for the things that cost money or need the internet: the AI, the vector store (Pinecone),
the embedding model and the outgoing email. Passwords, tokens, the database, file encryption and every route
are the real ones."""
import contextlib
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, text

from omnidoc.api import deps
from omnidoc.api.main import app
from omnidoc.core.config import get_settings
from omnidoc.db.models import User
from omnidoc.db.session import SessionLocal
from omnidoc.providers.email.base import EmailError
from omnidoc.providers.email.factory import SendResult
from omnidoc.services import email_service
from scripts.api_fakes import FakeEmbedder, FakeVectorStore
from tests.helpers import PASSWORD, ScriptedLLM, aadhaar_pdf, fake_aadhaar


class World:
    """Everything an integration test needs, shared by the whole run."""

    def __init__(self, tag):
        self.tag, self.settings = tag, get_settings()
        self.client = None
        self.store, self.embedder, self.llm = FakeVectorStore(), FakeEmbedder(), ScriptedLLM()
        self.sent, self.fail_email = [], {"on": False}
        self.created, self._counter = [], 0
        self._real_llm_for = deps.llm_for

    # --- users -------------------------------------------------------------------------------------------
    def new_user(self, prefix="u", email=None):
        self._counter += 1
        name = f"test_{prefix}{self._counter}_{self.tag}"
        body = {"username": name, "password": PASSWORD}
        if email:
            body["email"] = email
        r = self.client.post("/auth/signup", json=body)
        assert r.status_code == 201, r.text
        self.created.append(name)
        r = self.client.post(
            "/auth/login", data={"username": name, "password": PASSWORD})
        assert r.status_code == 200, r.text
        token = r.json()["access_token"]
        return SimpleNamespace(name=name, token=token, email=email, headers={"Authorization": f"Bearer {token}"})

    def upload(self, user, filename, data, mime="application/pdf", **form):
        return self.client.post("/documents", headers=user.headers, files={"file": (filename, data, mime)},
                                data={k: str(v) for k, v in form.items()})

    def user_with_aadhaar(self, prefix="u", email=None):
        user = self.new_user(prefix, email)
        number = fake_aadhaar()
        pdf = aadhaar_pdf(number)
        r = self.upload(user, "aadhaar.pdf", pdf)
        assert r.status_code == 201, r.text
        user.doc = SimpleNamespace(
            id=r.json()["document_id"], number=number, pdf=pdf)
        return user

    # --- test controls -------------------------------------------------------------------------------------
    @staticmethod
    def reset_limits():
        deps.limiter._hits.clear()
        deps.limiter._expires.clear()

    @contextlib.contextmanager
    def real_llm(self):
        """Use the server's real provider choice logic (for checking unknown-provider errors)."""
        deps.llm_for = self._real_llm_for
        try:
            yield
        finally:
            deps.llm_for = lambda provider: self.llm


@pytest.fixture(scope="session")
def world():
    try:
        with SessionLocal() as db:
            db.execute(text("select 1"))
    except Exception as exc:                                    # no database: skip, don't fail
        pytest.skip(
            f"database not reachable ({type(exc).__name__}); set DATABASE_URL to run integration tests")

    w = World(uuid.uuid4().hex[:6])

    def fake_send(providers, message):
        if w.fail_email["on"]:
            raise EmailError("all providers", "smtp: login rejected")
        w.sent.append(message)
        return SendResult("fake", [])

    mp = pytest.MonkeyPatch()
    app.dependency_overrides[deps.embedder_dep] = lambda: w.embedder
    app.dependency_overrides[deps.store_dep] = lambda: w.store
    mp.setattr(deps, "llm_for", lambda provider: w.llm)
    # nothing is ever really sent
    mp.setattr(email_service, "send_with_fallback", fake_send)
    mp.setattr(email_service, "provider_order",
               lambda preferred, needs_attachment: ["smtp"])
    mp.setattr(email_service, "get_email_provider", lambda name: object())
    # many test users come from one address
    mp.setattr(w.settings, "signup_per_hour_per_ip", 1000)
    try:
        # relative paths are under /v1
        with TestClient(app, base_url="http://testserver/v1") as client:
            w.client = client
            yield w
    finally:
        app.dependency_overrides.clear()
        mp.undo()
        with SessionLocal() as db:
            if w.created:
                db.execute(delete(User).where(User.username.in_(w.created)))
                db.commit()


@pytest.fixture(autouse=True)
def _fresh_limits(world):
    """Each test starts with empty rate-limit counters, so a lock-out test cannot affect the next test."""
    world.reset_limits()
    yield
    world.reset_limits()


@pytest.fixture(scope="session")
def alice(world):
    user = world.user_with_aadhaar(
        "alice", email=f"alice_{world.tag}@example.com")
    return user


@pytest.fixture(scope="session")
def bob(world):
    return world.new_user("bob")
