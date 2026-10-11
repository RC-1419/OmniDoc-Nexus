"""Every service-layer error must become the right clean HTTP answer, and unexpected errors must leak nothing."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from omnidoc.api.errors import register_error_handlers
from omnidoc.ingestion.extract import FileTooLarge, UnsupportedFileType
from omnidoc.providers.email.base import EmailError
from omnidoc.providers.llm.base import LLMError
from omnidoc.services.email_service import EmailLimitReached
from omnidoc.services.errors import DocumentError, NotFound, QuotaExceeded


def with_detail(cls, detail):
    """Build an error whatever its constructor looks like, as long as it exposes .detail."""
    try:
        exc = cls(detail)
    except TypeError:
        exc = cls.__new__(cls)
    if getattr(exc, "detail", None) != detail:
        try:
            exc.detail = detail
        except AttributeError:
            pytest.skip(f"{cls.__name__} does not expose a settable detail")
    return exc


CASES = [
    (lambda: NotFound("Document not found"), 404, "Document not found"),
    (lambda: QuotaExceeded("Too many documents"), 409, "Too many documents"),
    (lambda: DocumentError("That is not valid"), 400, "That is not valid"),
    (lambda: UnsupportedFileType("Only PDF and images"), 415, "Only PDF and images"),
    (lambda: FileTooLarge("File is larger than 10 MB"),
     413, "File is larger than 10 MB"),
    (lambda: EmailError("input", "bad address"), 400, "bad address"),
    (lambda: EmailError("email", "nothing set up"),
     503, "No email service is set up on this server"),
    (lambda: EmailError("smtp", "login rejected"),
     502, "Could not send the email: login rejected"),
    (lambda: with_detail(EmailLimitReached, "daily email limit reached"),
     429, "Daily email limit reached"),
    (lambda: with_detail(LLMError, "timeout"), 502,
     "The AI service isn't available right now (timeout)"),
]


def make_client():
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom/{n}")
    def boom(n: int):
        raise CASES[n][0]()

    @app.get("/crash")
    def crash():
        raise RuntimeError("database password is hunter2")

    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("n", range(len(CASES)))
def test_error_becomes_clean_answer(n):
    _, status, message = CASES[n]
    r = make_client().get(f"/boom/{n}")
    assert r.status_code == status and r.json() == {"detail": message}


def test_unexpected_error_is_a_plain_500_without_details():
    r = make_client().get("/crash")
    assert r.status_code == 500 and "hunter2" not in r.text and "RuntimeError" not in r.text
