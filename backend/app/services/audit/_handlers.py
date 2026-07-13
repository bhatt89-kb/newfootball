"""
Domain-specific audit event handler methods for :class:`AuditLogger`.

This mixin contains all the named log methods (``log_admin_action``,
``log_ai_prompt``, etc.) so that :mod:`app.services.audit.logger` stays
focused on the core ``log_event`` dispatcher and class infrastructure.

The mixin is not intended to be used directly — it is inherited by
:class:`~app.services.audit.logger.AuditLogger`.
"""
from __future__ import annotations

from typing import Any, Optional

from app.services.audit.types import AuditEventType, AuditSeverity

# ---------------------------------------------------------------------------
# Constants (shared with logger.py via this module)
# ---------------------------------------------------------------------------

#: Maximum characters of an AI prompt preview written to the audit log.
PROMPT_PREVIEW_MAX_CHARS: int = 200

#: Maximum characters of a stack trace written to the audit log.
STACK_TRACE_MAX_CHARS: int = 500

#: Severity strings treated as "high-severity" incidents.
HIGH_SEVERITY_LABELS: frozenset[str] = frozenset({"high", "critical"})


class AuditEventHandlerMixin:
    """
    Mixin providing domain-specific audit log methods for :class:`AuditLogger`.

    Each method is a thin, semantically-named wrapper around ``self.log_event``
    so callers never need to choose ``AuditEventType`` or ``AuditSeverity``
    values directly — that mapping is encapsulated here.
    """

    # Subclass must provide this — it is defined in AuditLogger.
    def log_event(self, *args, **kwargs) -> None:  # type: ignore[override]
        raise NotImplementedError  # pragma: no cover

    def log_admin_action(
        self,
        action: str,
        admin_key_hash: str,
        ip_address: str,
        details: Optional[dict[str, Any]] = None,
        success: bool = True,
    ) -> None:
        """
        Record an administrative action such as a cache flush or config change.

        Args:
            action: Human-readable description of the action performed.
            admin_key_hash: Truncated hash of the admin API key (never the raw key).
            ip_address: Client IP address of the administrator.
            details: Additional context to merge into the log entry.
            success: Whether the action completed successfully.
        """
        event_type = (
            AuditEventType.ADMIN_LOGIN if "login" in action.lower()
            else AuditEventType.CONFIG_CHANGE
        )
        self.log_event(
            event_type=event_type,
            severity=AuditSeverity.WARNING if not success else AuditSeverity.INFO,
            user_id=f"admin_{admin_key_hash[:8]}",
            ip_address=ip_address,
            details={"action": action, **(details or {})},
            success=success,
        )

    def log_ai_prompt(
        self,
        prompt_preview: str,
        user_role: str,
        language: str,
        ip_address: str,
        cached: bool = False,
        success: bool = True,
    ) -> None:
        """
        Record an AI prompt dispatch for safety monitoring and compliance.

        Truncates the prompt to :data:`PROMPT_PREVIEW_MAX_CHARS` to preserve
        fan privacy while retaining enough context for a safety review.

        Args:
            prompt_preview: The raw prompt text (truncated automatically).
            user_role: Role of the fan or staff member who triggered the request.
            language: BCP-47 language code of the request.
            ip_address: Client IP address.
            cached: ``True`` when the response was served from Redis cache.
            success: Whether the AI call succeeded.
        """
        safe_preview = (
            prompt_preview[:PROMPT_PREVIEW_MAX_CHARS] + "..."
            if len(prompt_preview) > PROMPT_PREVIEW_MAX_CHARS
            else prompt_preview
        )
        self.log_event(
            event_type=AuditEventType.AI_RESPONSE_CACHED if cached else AuditEventType.AI_PROMPT,
            severity=AuditSeverity.INFO,
            ip_address=ip_address,
            details={"prompt_preview": safe_preview, "user_role": user_role, "language": language, "cached": cached},
            success=success,
        )

    def log_incident_report(
        self,
        incident_type: str,
        severity: str,
        location: str,
        reporter_ip: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Record a fan- or staff-submitted incident report.

        Args:
            incident_type: Category of the incident (e.g. ``"crowd_crush"``).
            severity: Perceived severity string (``"low"``, ``"high"``, etc.).
            location: Venue zone or free-text location of the incident.
            reporter_ip: IP address of the reporter.
            details: Additional context to merge into the log entry.
        """
        audit_sev = AuditSeverity.WARNING if severity in HIGH_SEVERITY_LABELS else AuditSeverity.INFO
        self.log_event(
            event_type=AuditEventType.INCIDENT_REPORT,
            severity=audit_sev,
            ip_address=reporter_ip,
            details={"incident_type": incident_type, "severity": severity, "location": location, **(details or {})},
            success=True,
        )

    def log_emergency_request(
        self,
        incident_type: str,
        severity: str,
        affected_zones: list[str],
        ip_address: str,
        escalated: bool = False,
    ) -> None:
        """
        Record an emergency response request for critical incident tracking.

        Args:
            incident_type: Type of emergency (e.g. ``"medical"``, ``"fire"``).
            severity: Perceived severity; ``"high"`` maps to CRITICAL audit level.
            affected_zones: List of zone IDs involved in the emergency.
            ip_address: Client IP address of the requestor.
            escalated: Whether the event was escalated to human responders.
        """
        audit_sev = AuditSeverity.CRITICAL if severity == "high" else AuditSeverity.WARNING
        self.log_event(
            event_type=AuditEventType.EMERGENCY_REQUEST,
            severity=audit_sev,
            ip_address=ip_address,
            details={"incident_type": incident_type, "severity": severity, "affected_zones": affected_zones, "escalated": escalated},
            success=True,
        )

    def log_rate_limit_exceeded(
        self,
        ip_address: str,
        endpoint: str,
        request_count: int,
    ) -> None:
        """
        Record a rate-limit violation for security monitoring.

        Args:
            ip_address: Client IP address that exceeded the limit.
            endpoint: API path that was rate-limited.
            request_count: Number of requests made within the window.
        """
        from app.config import get_settings  # imported here to avoid circular deps
        s = get_settings()
        self.log_event(
            event_type=AuditEventType.RATE_LIMIT_EXCEEDED,
            severity=AuditSeverity.WARNING,
            ip_address=ip_address,
            details={"endpoint": endpoint, "request_count": request_count, "limit": s.rate_limit_requests, "window_seconds": s.rate_limit_window_seconds},
            success=False,
        )

    def log_auth_failure(self, reason: str, ip_address: str, attempted_endpoint: str) -> None:
        """
        Record an authentication failure for security monitoring.

        Args:
            reason: Human-readable description of why authentication failed.
            ip_address: Client IP address of the failed attempt.
            attempted_endpoint: API path the client was trying to reach.
        """
        self.log_event(
            event_type=AuditEventType.AUTH_FAILURE,
            severity=AuditSeverity.WARNING,
            ip_address=ip_address,
            details={"reason": reason, "endpoint": attempted_endpoint},
            success=False,
        )

    def log_crowd_analysis(self, zones_analyzed: list[str], alerts_generated: int, operator_ip: str) -> None:
        """
        Record a crowd-analysis operation for operational tracking.

        Severity is elevated to WARNING when at least one alert was generated.

        Args:
            zones_analyzed: List of zone IDs included in the analysis run.
            alerts_generated: Count of non-low-severity alerts raised.
            operator_ip: IP address of the requesting operator.
        """
        self.log_event(
            event_type=AuditEventType.CROWD_ANALYSIS,
            severity=AuditSeverity.WARNING if alerts_generated > 0 else AuditSeverity.INFO,
            ip_address=operator_ip,
            details={"zones_analyzed": zones_analyzed, "alerts_generated": alerts_generated},
            success=True,
        )

    def log_error(
        self,
        error_type: str,
        error_message: str,
        endpoint: str,
        ip_address: Optional[str] = None,
        stack_trace: Optional[str] = None,
    ) -> None:
        """
        Record an application error for debugging and monitoring.

        Stack traces are truncated to :data:`STACK_TRACE_MAX_CHARS` characters.

        Args:
            error_type: Exception class name or short category label.
            error_message: The exception message string.
            endpoint: API path where the error occurred.
            ip_address: Client IP address (if available).
            stack_trace: Full traceback string (truncated before logging).
        """
        self.log_event(
            event_type=AuditEventType.ERROR,
            severity=AuditSeverity.ERROR,
            ip_address=ip_address,
            details={
                "error_type": error_type,
                "error_message": error_message,
                "endpoint": endpoint,
                "stack_trace": stack_trace[:STACK_TRACE_MAX_CHARS] if stack_trace else None,
            },
            success=False,
        )
