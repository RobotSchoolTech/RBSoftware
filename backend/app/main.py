import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DataError, StatementError

from app.api.router import api_router
from app.core.config import settings
from app.core.storage import storage_service

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        root_path="/api",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:8080",
            "https://lms.miel-robotschool.com",
            "https://app.miel-robotschool.com",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)

    @app.exception_handler(StatementError)
    @app.exception_handler(DataError)
    async def sqlalchemy_error_handler(request: Request, exc: Exception):
        logger.exception("Error de base de datos en %s %s", request.method, request.url.path)
        return JSONResponse(status_code=400, content={"detail": "Datos inválidos en la solicitud."})

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        logger.warning("ValueError en %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.on_event("startup")
    async def startup():
        storage_service.ensure_bucket_exists()

    return app


app = create_app()
