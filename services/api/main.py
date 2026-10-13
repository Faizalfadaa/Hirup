from importlib.metadata import version

from fastapi import APIRouter, FastAPI

from services.api.routes import health


def create_app() -> FastAPI:
    app = FastAPI(title="Hirup API", version=version("hirup"))
    v1 = APIRouter(prefix="/v1")
    v1.include_router(health.router)
    app.include_router(v1)
    return app


app = create_app()
