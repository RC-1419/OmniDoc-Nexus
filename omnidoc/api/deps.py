from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from omnidoc.core.config import get_settings
from omnidoc.core.ratelimit import RateLimiter
from omnidoc.core.security import decode_access_token
from omnidoc.db.models import User
from omnidoc.db.session import get_db
from omnidoc.providers.embeddings.base import Embedder
from omnidoc.providers.embeddings.factory import get_embedder
from omnidoc.providers.llm.factory import configured_providers, get_llm_for_user_choice
from omnidoc.providers.storage.base import FileStore
from omnidoc.providers.storage.factory import get_file_store
from omnidoc.providers.vectorstore.base import VectorStore
from omnidoc.providers.vectorstore.factory import get_vector_store

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
DB = Annotated[Session, Depends(get_db)]


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: DB) -> User:
    user_id = decode_access_token(token)
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token",
                            headers={"WWW-Authenticate": "Bearer"})
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


# Separate functions so tests (or a different deployment) can swap any of them with dependency_overrides.
def embedder_dep() -> Embedder:
    return get_embedder()


def store_dep() -> VectorStore:
    return get_vector_store()


def files_dep() -> FileStore:
    return get_file_store()


Embeds = Annotated[Embedder, Depends(embedder_dep)]
Vectors = Annotated[VectorStore, Depends(store_dep)]
Files = Annotated[FileStore, Depends(files_dep)]


def llm_for(provider: str | None):
    """The AI provider the user picked, or the server's default. Only providers with a key are allowed."""
    configured = configured_providers()
    if not configured:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "No AI provider is configured on this server")
    if provider:
        choice = provider.strip().lower()
        if choice not in configured:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                "That AI provider isn't available")
    else:
        default = get_settings().default_llm
        choice = default if default in configured else configured[0]
    return get_llm_for_user_choice(choice)


limiter = RateLimiter()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def too_many(wait: int) -> HTTPException:
    return HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, f"Too many requests. Try again in {wait} seconds.",
                         headers={"Retry-After": str(wait)})


def enforce(key: str, limit: int, window_seconds: int) -> None:
    wait = limiter.hit(key, limit, window_seconds)
    if wait:
        raise too_many(wait)
