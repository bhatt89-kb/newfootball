"""
Enumeration types for the StadiumOS audit logging subsystem.

Keeping enums in a dedicated module allows them to be imported by any
layer (routers, services, tests) without pulling in the heavier
:mod:`app.services.audit.logger` or its transitive dependencies.
"""
from __future__ import annotations

from enum import Enum


class AuditEventType(str, Enum):
    """
    Canonical event-type labels written to every audit log entry.

    Values are lower-snake-case strings so they are safe to use as SIEM
    field values, Elasticsearch field values, or BigQuery column names
    without any further transformation.
    """

    # Authentication & Authorization
    ADMIN_LOGIN = "admin_login"
    ADMIN_LOGOUT = "admin_logout"
    AUTH_FAILURE = "auth_failure"

    # AI Operations
    AI_PROMPT = "ai_prompt"
    AI_RESPONSE_CACHED = "ai_response_cached"
    AI_FALLBACK_USED = "ai_fallback_used"

    # Admin Operations
    CACHE_FLUSH = "cache_flush"
    CONFIG_CHANGE = "config_change"
    SYSTEM_STATUS_CHECK = "system_status_check"

    # User Actions
    NAVIGATION_REQUEST = "navigation_request"
    CHAT_REQUEST = "chat_request"
    INCIDENT_REPORT = "incident_report"
    EMERGENCY_REQUEST = "emergency_request"
    ACCESSIBILITY_REQUEST = "accessibility_request"

    # Volunteer / Staff Actions
    VOLUNTEER_ACTION = "volunteer_action"
    CROWD_ANALYSIS = "crowd_analysis"
    TRANSPORT_UPDATE = "transport_update"

    # System Events
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    ERROR = "error"
    SERVICE_START = "service_start"
    SERVICE_STOP = "service_stop"


class AuditSeverity(str, Enum):
    """
    Severity levels for audit events, aligned with standard syslog priorities.

    The ``ERROR`` member intentionally shares its name with
    :attr:`AuditEventType.ERROR` but represents a log-level concept, not an
    event-type concept — keep the two enums distinct when calling
    :meth:`~app.services.audit.logger.AuditLogger.log_event`.
    """

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
