"""
Public API for the StadiumOS audit logging subsystem.

This package is split into three focused modules:

* :mod:`app.services.audit.types`  — ``AuditEventType`` and ``AuditSeverity`` enums.
* :mod:`app.services.audit.logger` — ``AuditLogger`` class with all domain methods.
* :mod:`app.services.audit`        — (this file) singleton accessor and convenience
                                      functions for one-liner call sites.

Importing from this package gives access to the full public surface::

    from app.services.audit import (
        get_audit_logger,
        log_admin_action,
        log_ai_prompt,
        AuditEventType,
        AuditSeverity,
    )
"""
from __future__ import annotations

from typing import Any, Optional

from app.services.audit.logger import AuditLogger
from app.services.audit.types import AuditEventType, AuditSeverity

# ---------------------------------------------------------------------------
# Re-exports — anything imported from this package's old flat location still
# works without any changes to existing call sites.
# ---------------------------------------------------------------------------
__all__ = [
    "AuditEventType",
    "AuditSeverity",
    "AuditLogger",
    "get_audit_logger",
    "log_admin_action",
    "log_ai_prompt",
    "log_incident_report",
    "log_emergency_request",
    "log_rate_limit_exceeded",
    "log_auth_failure",
]

# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """
    Return the process-wide :class:`~app.services.audit.logger.AuditLogger` instance.

    Initialises the instance on first call (lazy singleton pattern).  Safe
    to call from any thread or async task — the singleton is created before
    concurrent access is possible in normal FastAPI startup.

    Returns:
        The shared :class:`AuditLogger` instance.
    """
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------

def log_admin_action(action: str, admin_key_hash: str, ip_address: str, **kwargs: Any) -> None:
    """
    Convenience wrapper: log an administrative action via the shared logger.

    Args:
        action: Human-readable description of the admin action.
        admin_key_hash: Truncated hash of the admin API key (never the raw key).
        ip_address: Client IP address of the administrator.
        **kwargs: Additional keyword arguments forwarded to
                  :meth:`~AuditLogger.log_admin_action`.
    """
    get_audit_logger().log_admin_action(action, admin_key_hash, ip_address, **kwargs)


def log_ai_prompt(
    prompt_preview: str,
    user_role: str,
    language: str,
    ip_address: str,
    **kwargs: Any,
) -> None:
    """
    Convenience wrapper: log an AI prompt dispatch via the shared logger.

    Args:
        prompt_preview: The raw prompt text (truncated automatically to 200 chars).
        user_role: Role of the user who triggered the AI call.
        language: BCP-47 language code of the request.
        ip_address: Client IP address.
        **kwargs: Additional keyword arguments forwarded to
                  :meth:`~AuditLogger.log_ai_prompt`.
    """
    get_audit_logger().log_ai_prompt(prompt_preview, user_role, language, ip_address, **kwargs)


def log_incident_report(
    incident_type: str,
    severity: str,
    location: str,
    reporter_ip: str,
    **kwargs: Any,
) -> None:
    """
    Convenience wrapper: log an incident report via the shared logger.

    Args:
        incident_type: Category of the incident.
        severity: Perceived severity (``"low"``, ``"high"``, etc.).
        location: Venue zone or free-text location string.
        reporter_ip: IP address of the reporter.
        **kwargs: Additional keyword arguments forwarded to
                  :meth:`~AuditLogger.log_incident_report`.
    """
    get_audit_logger().log_incident_report(incident_type, severity, location, reporter_ip, **kwargs)


def log_emergency_request(
    incident_type: str,
    severity: str,
    affected_zones: list[str],
    ip_address: str,
    **kwargs: Any,
) -> None:
    """
    Convenience wrapper: log an emergency request via the shared logger.

    Args:
        incident_type: Type of emergency (e.g. ``"medical"``, ``"fire"``).
        severity: Perceived severity string; ``"high"`` maps to CRITICAL.
        affected_zones: List of zone IDs involved in the emergency.
        ip_address: Client IP address of the requestor.
        **kwargs: Additional keyword arguments forwarded to
                  :meth:`~AuditLogger.log_emergency_request`.
    """
    get_audit_logger().log_emergency_request(incident_type, severity, affected_zones, ip_address, **kwargs)


def log_rate_limit_exceeded(ip_address: str, endpoint: str, request_count: int) -> None:
    """
    Convenience wrapper: log a rate-limit violation via the shared logger.

    Args:
        ip_address: Client IP address that exceeded the limit.
        endpoint: API path that was rate-limited.
        request_count: Number of requests made within the current window.
    """
    get_audit_logger().log_rate_limit_exceeded(ip_address, endpoint, request_count)


def log_auth_failure(reason: str, ip_address: str, attempted_endpoint: str) -> None:
    """
    Convenience wrapper: log an authentication failure via the shared logger.

    Args:
        reason: Human-readable description of why authentication failed.
        ip_address: Client IP address of the failed attempt.
        attempted_endpoint: API path the client was trying to reach.
    """
    get_audit_logger().log_auth_failure(reason, ip_address, attempted_endpoint)
