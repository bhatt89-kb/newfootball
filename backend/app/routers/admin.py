"""
Admin-only router for StadiumOS GenAI operational endpoints.

All routes require a valid ``X-Admin-Key`` header (see
:func:`app.security.require_admin_key`).  They are intentionally excluded
from the public OpenAPI schema and are designed for use by the operations
team or automated monitoring infrastructure only.

Endpoints
---------
GET  /admin/status       — Deployment health and GenAI/cache status.
GET  /admin/cache/stats  — Detailed Redis cache statistics.
POST /admin/cache/flush  — Flush cache entries matching a key pattern.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import get_settings
from app.security import require_admin_key
from app.services.ai_service import is_ai_available
from app.services.cache import get_cache_stats, is_cache_available, flush_cache

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin_key)])
settings = get_settings()


@router.get("/status")
async def status() -> dict:
    """
    Deployment status check for operations and monitoring teams.

    Returns a snapshot of the service's health including GenAI and cache
    availability, rate-limit configuration, and the current environment.
    Requires the ``X-Admin-Key`` header.

    Returns:
        A dict with ``app_name``, ``environment``, ``genai_available``,
        ``cache_available``, ``cache_stats``, and ``rate_limit``.
    """
    cache_stats = await get_cache_stats()
    cache_available = await is_cache_available()
    return {
        "app_name": settings.app_name,
        "environment": settings.environment,
        "genai_available": is_ai_available(),
        "cache_available": cache_available,
        "cache_stats": cache_stats,
        "rate_limit": f"{settings.rate_limit_requests} req / {settings.rate_limit_window_seconds}s",
    }


@router.get("/cache/stats")
async def cache_stats() -> dict:
    """
    Retrieve detailed Redis cache statistics.

    Returns:
        A dict with raw Redis stats and a human-readable performance
        recommendation based on the current hit rate.
    """
    stats = await get_cache_stats()
    return {
        "cache": stats,
        "recommendation": "Consider increasing cache TTL if hit rate < 70%" if stats.get("hit_rate", 100) < 70 else "Cache performance is healthy"
    }


@router.post("/cache/flush")
async def flush_cache_endpoint(pattern: str = "*") -> dict:
    """
    Flush Redis cache entries whose keys match ``pattern``.

    Uses Redis ``KEYS`` + ``DEL`` so should be called with a specific prefix
    pattern in production rather than ``"*"`` to avoid accidental full-cache
    eviction.  Requires the ``X-Admin-Key`` header.

    Args:
        pattern: Redis key-glob pattern (default ``"*"`` flushes everything).
                 Examples: ``"ai_response:*"``, ``"navigation:*"``.

    Returns:
        A dict with ``flushed`` (count of deleted keys), ``pattern``, and
        a human-readable ``message``.
    """
    deleted_count = await flush_cache(pattern)
    return {
        "flushed": deleted_count,
        "pattern": pattern,
        "message": f"Successfully flushed {deleted_count} cache entries"
    }
