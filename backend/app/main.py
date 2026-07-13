"""
StadiumOS GenAI — FastAPI application entrypoint.

Run locally:
    uvicorn app.main:app --reload --port 8000

See docs/ARCHITECTURE.md for the full system design and
docs/SECURITY.md for the threat model behind the middleware stack below.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import get_settings
from app.routers import admin, api
from app.security import BodySizeLimitMiddleware, SecurityHeadersMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("stadiumos.main")

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="GenAI-enabled stadium operations & fan-experience platform for FIFA World Cup 2026 host venues.",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# --- Middleware (order matters: outermost first) --------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Admin-Key"],
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(BodySizeLimitMiddleware)


# --- Global, information-minimal error handlers ---------------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Convert Pydantic validation errors into a structured, frontend-friendly JSON response.

    Returns field-level error details useful for the frontend form validation, but
    never leaks internal stack traces, file paths, or implementation details.

    Args:
        request: The incoming request that triggered the validation error.
        exc: The RequestValidationError raised by FastAPI/Pydantic.

    Returns:
        JSONResponse with HTTP 422 and a list of field-level error objects.
    """
    errors = [{"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": "Invalid request.", "errors": errors})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Last-resort handler for any unhandled exception reaching the ASGI layer.

    Logs the full traceback server-side for diagnostics while returning an
    opaque 500 message to the client so no internal details are exposed.

    Args:
        request: The incoming request that caused the exception.
        exc: The unhandled exception instance.

    Returns:
        JSONResponse with HTTP 500 and a generic error message.
    """
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred. Our team has been notified."})


# --- Routers ----------------------------------------------------------------
app.include_router(api.router)
app.include_router(admin.router)


@app.get("/")
async def root() -> dict[str, str]:
    """
    Service discovery endpoint returning key URLs for this deployment.

    Returns:
        A dict with ``service`` name, ``status``, ``docs`` URL, and
        ``health`` probe URL.
    """
    return {
        "service": settings.app_name,
        "status": "operational",
        "docs": "/api/docs",
        "health": "/api/v1/health",
    }


# --- Prometheus Metrics -----------------------------------------------------
# Expose metrics at /metrics for monitoring systems
if settings.environment != "development":
    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
