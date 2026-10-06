from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from omnidoc.ingestion.extract import FileTooLarge, UnsupportedFileType
from omnidoc.providers.email.base import EmailError
from omnidoc.providers.llm.base import LLMError
from omnidoc.services.email_service import EmailLimitReached
from omnidoc.services.errors import DocumentError, NotFound, QuotaExceeded


def _json(status_code: int, message: str) -> JSONResponse:
    return JSONResponse({"detail": message}, status_code=status_code)


def register_error_handlers(app: FastAPI) -> None:
    """Turn the service layer's errors into clean HTTP answers. Unexpected errors are not caught here:
    they become a plain 500 with no details."""

    @app.exception_handler(NotFound)
    async def not_found(request: Request, exc: NotFound):
        # also used when the item belongs to someone else
        return _json(404, str(exc))

    @app.exception_handler(QuotaExceeded)
    async def quota(request: Request, exc: QuotaExceeded):
        return _json(409, str(exc))

    @app.exception_handler(DocumentError)
    async def document_error(request: Request, exc: DocumentError):
        return _json(400, str(exc))

    @app.exception_handler(UnsupportedFileType)
    async def unsupported(request: Request, exc: UnsupportedFileType):
        return _json(415, str(exc))

    @app.exception_handler(FileTooLarge)
    async def too_large(request: Request, exc: FileTooLarge):
        return _json(413, str(exc))

    @app.exception_handler(EmailLimitReached)
    async def email_limit(request: Request, exc: EmailLimitReached):
        return _json(429, exc.detail[:1].upper() + exc.detail[1:])

    @app.exception_handler(EmailError)
    async def email_error(request: Request, exc: EmailError):
        if exc.provider == "input":
            return _json(400, exc.detail)
        if exc.provider == "email":
            return _json(503, "No email service is set up on this server")
        return _json(502, f"Could not send the email: {exc.detail}")

    @app.exception_handler(LLMError)
    async def llm_error(request: Request, exc: LLMError):
        return _json(502, f"The AI service isn't available right now ({exc.detail})")
