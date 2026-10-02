from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from omnidoc.core.config import get_settings
from omnidoc.db.models import Base

engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db():
    """FastAPI dependency: one session per request."""
    with SessionLocal() as db:
        yield db


def init_db() -> None:
    Base.metadata.create_all(engine)
