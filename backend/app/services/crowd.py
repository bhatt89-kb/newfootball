"""
Crowd-density analysis service for StadiumOS GenAI.

Applies deterministic threshold rules to classify each submitted zone
reading as ``low``, ``medium``, ``high``, or ``critical``, generates
operator-facing alerts for any non-low zone, then asks Gemini to produce
a tight triage summary for the stadium control room.

Design principles
-----------------
* **Safety-critical determinism**: Threshold checks and alert generation are
  pure, synchronous functions with zero network dependencies.  Crowd alerts
  fire even when the GenAI provider is completely unavailable.
* **Operator-first ordering**: Alerts are always sorted by severity so that
  the most urgent zone appears first in the response.
* **Minimal AI surface**: The GenAI call is skipped entirely when all zones
  are within safe thresholds — the fallback "all clear" message is already
  the ideal text in that case.
"""
from __future__ import annotations

from typing import List

from app.data.stadium_map import zone_display_name
from app.schemas import CrowdAlert, CrowdAnalysisRequest, CrowdAnalysisResponse
from app.security import sanitize_user_text
from app.services import ai_service

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Ordered thresholds: (min_occupancy_percent, severity_label, operator_action).
#: Evaluated top-to-bottom; first matching threshold wins.
_THRESHOLDS: list[tuple[int, str, str]] = [
    (95, "critical", "Immediate action required: halt inflow and open overflow route."),
    (85, "high",     "Deploy additional stewards and open an alternate concourse."),
    (70, "medium",   "Monitor closely; consider soft crowd redirection."),
    (0,  "low",      "No action required."),
]

#: Severity ordering used to sort alerts for operator triage (lower = more urgent).
_SEVERITY_ORDER: dict[str, int] = {"critical": 0, "high": 1, "medium": 2, "low": 3}

#: Maximum tokens requested from the GenAI model for crowd summaries.
_SUMMARY_MAX_TOKENS: int = 150


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _classify(occupancy: float) -> tuple[str, str]:
    """
    Classify a zone's occupancy percentage into a severity level and action.

    Iterates through :data:`_THRESHOLDS` top-to-bottom and returns the first
    match.  The last entry (threshold 0) acts as a catch-all fallback so this
    function always returns a valid pair.

    Args:
        occupancy: Zone occupancy as a percentage (0–100).

    Returns:
        A ``(severity, recommended_action)`` tuple.
    """
    for threshold, severity, action in _THRESHOLDS:
        if occupancy >= threshold:
            return severity, action
    return "low", "No action required."


def _fallback_summary(alerts: List[CrowdAlert]) -> str:
    """
    Build a plain-text crowd summary without GenAI.

    Args:
        alerts: List of alerts already sorted by severity (most urgent first).

    Returns:
        A concise operator-facing summary string.
    """
    if not alerts:
        return "All monitored zones are within safe capacity thresholds. No operator action needed."
    critical = [a for a in alerts if a.severity == "critical"]
    if critical:
        zones = ", ".join(zone_display_name(a.zone_id) for a in critical)
        return f"URGENT: {zones} at critical capacity. Dispatch stewards and open overflow routes immediately."
    return f"{len(alerts)} zone(s) require attention. Highest priority: {alerts[0].message}"


# ---------------------------------------------------------------------------
# Public service function
# ---------------------------------------------------------------------------

async def analyze_crowd(req: CrowdAnalysisRequest) -> CrowdAnalysisResponse:
    """
    Analyse submitted zone readings and produce prioritised crowd alerts.

    For each zone in the request, applies the deterministic threshold rules
    to classify severity.  Zones at ``"low"`` severity are excluded from the
    alert list.  The remaining alerts are sorted most-urgent-first, then a
    GenAI summary is requested for the operator.

    Args:
        req: Validated crowd analysis request containing one or more zone
             readings and the current event phase.

    Returns:
        CrowdAnalysisResponse with a sorted list of alerts and an overall
        operational summary.  The ``source`` field is ``"genai"`` when Gemini
        produced the summary, or ``"fallback"`` otherwise.
    """
    alerts: List[CrowdAlert] = []
    for zone in req.zones:
        severity, action = _classify(zone.occupancy_percent)
        if severity == "low":
            continue
        alerts.append(
            CrowdAlert(
                zone_id=zone.zone_id,
                severity=severity,
                message=(
                    f"{zone_display_name(zone.zone_id)} is at {zone.occupancy_percent:.0f}% capacity "
                    f"(inflow {zone.inflow_rate:+.0f}/min)."
                ),
                recommended_action=action,
            )
        )

    # Highest severity first for operator triage.
    alerts.sort(key=lambda a: _SEVERITY_ORDER[a.severity])

    summary = await _generate_summary(req, alerts)
    source = "genai" if summary else "fallback"
    if not summary:
        summary = _fallback_summary(alerts)

    return CrowdAnalysisResponse(alerts=alerts, overall_summary=summary, source=source)


async def _generate_summary(req: CrowdAnalysisRequest, alerts: List[CrowdAlert]) -> str | None:
    """
    Ask Gemini to write a tight operator triage summary for the given alerts.

    Returns early (``None``) when there are no alerts, since the fallback
    "all clear" text is already optimal in that case.

    Args:
        req: The original crowd analysis request (used for event phase context).
        alerts: The list of active crowd alerts, sorted by severity.

    Returns:
        A GenAI-generated summary paragraph, or ``None`` if there are no alerts
        or if GenAI is unavailable.
    """
    if not alerts:
        return None  # Fallback text is already the ideal "all clear" message; skip the AI call.
    system_prompt = (
        "You are an operations-intelligence assistant for FIFA World Cup 2026 stadium control room staff. "
        "Given a list of crowd alerts, produce a single tight paragraph (max 60 words) an operator can read "
        "in 5 seconds during a live match: state the biggest risk first, then the recommended action. "
        "Be concrete and calm. No filler, no apologies."
    )
    alerts_text = "\n".join(
        f"- [{a.severity.upper()}] {a.message} Action: {a.recommended_action}" for a in alerts
    )
    user_prompt = (
        f"Event phase: {sanitize_user_text(req.event_phase)}\n"
        f"Alerts:\n{sanitize_user_text(alerts_text)}"
    )
    return await ai_service.generate(system_prompt, user_prompt, max_tokens=_SUMMARY_MAX_TOKENS)
