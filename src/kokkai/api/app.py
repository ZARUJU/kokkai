from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from kokkai.api.routes import diet_sessions
from kokkai.api.routes import health
from kokkai.db.schema import create_all


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    create_all()
    yield


app = FastAPI(title="kokkai", lifespan=lifespan)
app.include_router(health.router)
app.include_router(diet_sessions.router)
