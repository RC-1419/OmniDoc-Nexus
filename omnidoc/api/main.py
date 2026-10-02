from contextlib import asynccontextmanager

from fastapi import FastAPI

from omnidoc.api.routes import auth
from omnidoc.core.config import get_settings
from omnidoc.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title=get_settings().app_name, lifespan=lifespan)
app.include_router(auth.router)


@app.get("/health")
def health():
    return {"status": "ok"}
