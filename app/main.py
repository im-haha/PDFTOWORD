from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import routes_download, routes_health, routes_tasks
from app.config import ensure_storage_dirs, settings
from app.models.init_db import init_db
from app.utils.errors import AppError, ERROR_CODES
from app.utils.logger import configure_logging, get_logger
from app.workers.convert_worker import convert_worker


configure_logging()
logger = get_logger(__name__)


app = FastAPI(title=settings.app_name)


@app.on_event("startup")
async def on_startup() -> None:
    ensure_storage_dirs()
    init_db()
    await convert_worker.start()
    logger.info("service started")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await convert_worker.stop()


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "code": exc.code,
            "message": exc.message,
            "data": None,
        },
    )


@app.exception_handler(Exception)
async def default_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "code": ERROR_CODES["DOCX_GENERATION_FAILED"],
            "message": "internal error",
            "data": None,
        },
    )


app.include_router(routes_health.router, prefix=settings.api_prefix)
app.include_router(routes_tasks.router, prefix=settings.api_prefix)
app.include_router(routes_download.router, prefix=settings.api_prefix)
