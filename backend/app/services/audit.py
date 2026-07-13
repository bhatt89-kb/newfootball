"""
Audit logging subsystem for StadiumOS GenAI.

.. deprecated::
    This file is superseded by the ``app/services/audit/`` package.
    Python resolves the package directory (``audit/``) before this module
    file, so this file is never imported at runtime.  It is retained only
    to explain the migration for contributors reading the directory listing.

    Import the audit subsystem from the package directly::

        from app.services.audit import get_audit_logger, log_ai_prompt
        from app.services.audit.types import AuditEventType, AuditSeverity
        from app.services.audit.logger import AuditLogger

Package layout
--------------
``audit/types.py``
    :class:`~app.services.audit.types.AuditEventType` and
    :class:`~app.services.audit.types.AuditSeverity` enums.

``audit/logger.py``
    :class:`~app.services.audit.logger.AuditLogger` — the core class with
    all domain-specific log methods.

``audit/__init__.py``
    Singleton accessor (:func:`~app.services.audit.get_audit_logger`) and
    module-level convenience functions for one-liner call sites.
"""
