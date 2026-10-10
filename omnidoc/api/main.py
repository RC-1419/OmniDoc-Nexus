from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from omnidoc.api.errors import register_error_handlers
from omnidoc.api.routes import auth, chat, documents, meta, people
from omnidoc.core import crypto
from omnidoc.core.config import get_settings
from omnidoc.db.session import init_db

settings = get_settings()

# bump only for breaking changes; the old version stays available next to the new one
API_VERSION = "1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    if len(settings.jwt_secret) < 32:  # fail at startup, not on the first login
        raise RuntimeError(
            "JWT_SECRET must be at least 32 characters (see .env.example)")
    # raises if VAULT_KEY is missing or invalid
    crypto.encrypt_text(0, "startup check")
    init_db()
    yield


app = FastAPI(
    title=settings.app_name, version=f"{API_VERSION}.0.0", lifespan=lifespan, redoc_url=None,
    docs_url="/docs" if settings.enable_docs else None,
    openapi_url="/openapi.json" if settings.enable_docs else None)


@app.middleware("http")
async def basic_protections(request: Request, call_next):
    # a little room for the multipart envelope
    limit = (settings.max_upload_mb + 1) * 1024 * 1024
    try:
        too_big = int(request.headers.get("content-length", "0")) > limit
    except ValueError:
        too_big = True
    if too_big:
        return JSONResponse({"detail": "Request too large"}, status_code=413)
    response = await call_next(request)
    response.headers.setdefault("Cache-Control", "no-store")
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-API-Version"] = API_VERSION
    return response


origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
if origins:  # added last = outermost, so even a "too large" answer carries the CORS headers a browser needs
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST", "PUT", "DELETE"],
                       allow_headers=["Authorization", "Content-Type"])

register_error_handlers(app)
v1 = APIRouter(prefix=f"/v{API_VERSION}")
for module in (meta, auth, people, documents, chat):
    v1.include_router(module.router)
app.include_router(v1)


# not versioned: used by Docker and monitoring
@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
