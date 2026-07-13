"""
Core :class:`AuditLogger` class for StadiumOS GenAI.

Responsibilities
----------------
* Build and serialise the structured JSON audit entry (see :meth:`log_event`).
* Route the entry to the correct Python :mod:`logging` level.
* Inherit all domain-specific log methods from
  :class:`~app.services.audit._handlers.AuditEventHandlerMixin`.

The enum types used here live in :mod:`app.services.audit.types`.
Module-level convenience functions are in :mod:`app.services.audit`.

Usage::

    from app.services.audit import get_audit_logger

    audit = get_audit_logger()
    audit.log_ai_prompt(prompt, user_role="fan", language="en", ip_address=ip)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from app.config import get_settings
from app.services.audit._handlers import AuditEventHandlerMixin
from app.services.audit.types import AuditEventType, AuditSeverity

settings = get_settings()


class AuditLogger(AuditEventHandlerMixin):
    """
    Centralised audit logger that emits structured JSON events.

    Inherits domain-specific log methods from
    :class:`~app.services.audit._handlers.AuditEventHandlerMixin`.
    All output is routed through the Python :mod:`logging` hierarchy so that
    production deployments can redirect the ``"stadiumos.audit.events"``
    logger to a separate file, a SIEM forwarder, or a cloud logging sink via
    standard ``logging`` configuration — no code changes required.
    """

    def __init__(self) -> None:
        """Initialise the dedicated audit event sub-logger."""
        self._logger = logging.getLogger("stadiumos.audit.events")
        self._logger.setLevel(logging.INFO)

    def log_event(
        self,
        event_type: AuditEventType,
        severity: AuditSeverity = AuditSeverity.INFO,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        success: bool = True,
    ) -> None:
        """
        Emit a structured JSON audit event at the appropriate log level.

        Builds a dictionary containing a UTC timestamp, event metadata, and
        caller-supplied details, serialises it as JSON, then dispatches to
        the matching Python logger method.

        Args:
            event_type: Category of the audited event.
            severity: Log severity; controls which Python log method is called.
            user_id: Identifier of the acting user (defaults to ``"anonymous"``).
            ip_address: Client IP address (defaults to ``"unknown"``).
            details: Arbitrary key/value context dict merged into the log entry.
            success: Whether the audited action completed successfully.
        """
        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type.value,
            "severity": severity.value,
            "success": success,
            "user_id": user_id or "anonymous",
            "ip_address": ip_address or "unknown",
            "environment": settings.environment,
            "details": details or {},
        }
        message = json.dumps(entry, default=str)

        # Dispatch to the appropriate log level; default to INFO.
        level_map = {
            AuditSeverity.CRITICAL: self._logger.critical,
            AuditSeverity.ERROR:    self._logger.error,
            AuditSeverity.WARNING:  self._logger.warning,
        }
        level_map.get(severity, self._logger.info)(message)
