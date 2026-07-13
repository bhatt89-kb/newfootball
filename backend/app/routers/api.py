"""
API router for StadiumOS GenAI public endpoints.

All routes are versioned under ``/api/v1`` and protected by the shared
sliding-window rate limiter (see :mod:`app.security`).

Endpoints
---------
POST /api/v1/chat            — Multilingual fan chat assistant.
POST /api/v1/navigate        — Indoor wayfinding / route planning.
POST /api/v1/crowd/analyze   — Real-time crowd-density analysis.
POST /api/v1/accessibility   — Accessibility guidance for fans.
POST /api/v1/translate       — Text translation across 10 languages.
POST /api/v1/sustainability  — Sustainability tips for fans.
POST /api/v1/emergency       — Emergency situation decision support.
POST /api/v1/transport       — Transport & parking recommendations.
GET  /api/v1/health          — Liveness probe.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app.schemas import (
    AccessibilityRequest, AccessibilityResponse,
    ChatRequest, ChatResponse,
    CrowdAnalysisRequest, CrowdAnalysisResponse,
    EmergencyRequest, EmergencyResponse,
    NavigationRequest, NavigationResponse,
    SustainabilityRequest, SustainabilityResponse,
    TranslateRequest, TranslateResponse,
    TransportRequest, TransportResponse,
)
from app.security import enforce_rate_limit
from app.services import accessibility, assistant, crowd, navigation, transport
from app.services.ai_service import is_ai_available

logger = logging.getLogger("stadiumos.api")
router = APIRouter(prefix="/api/v1", tags=["stadiumos"])

# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------

def _rate_limited(request: Request) -> None:
    """FastAPI dependency that enforces per-IP rate limiting on every call."""
    enforce_rate_limit(request)


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------

@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(_rate_limited)])
async def chat_endpoint(payload: ChatRequest) -> ChatResponse:
    """
    Multilingual fan chat assistant powered by Gemini.

    Accepts a fan's free-text message and returns a contextual reply along
    with suggested follow-up actions (e.g. open navigation, accessibility info).
    Falls back to a canned FAQ response if GenAI is unavailable.

    Args:
        payload: Validated chat request including message, language, and fan role.

    Returns:
        ChatResponse with reply text, language, suggested actions, and source tag.

    Raises:
        HTTPException: 500 if the assistant service encounters an unexpected error.
    """
    try:
        return await assistant.chat(payload)
    except Exception:
        logger.exception("chat_endpoint failed")
        raise HTTPException(status_code=500, detail="The assistant is temporarily unavailable. Please try again.")


@router.post("/navigate", response_model=NavigationResponse, dependencies=[Depends(_rate_limited)])
async def navigate_endpoint(payload: NavigationRequest) -> NavigationResponse:
    """
    Indoor wayfinding between any two zones in the venue graph.

    Runs Dijkstra on the static stadium graph, then asks GenAI to narrate
    the steps in plain language. Returns step-by-step instructions with
    crowd levels and estimated walking times.

    Args:
        payload: Origin zone, destination zone, accessibility needs, and language.

    Returns:
        NavigationResponse with structured steps, total time, and a narrative.

    Raises:
        HTTPException: 500 if the navigation service encounters an unexpected error.
    """
    try:
        return await navigation.get_navigation(payload)
    except Exception:
        logger.exception("navigate_endpoint failed")
        raise HTTPException(status_code=500, detail="Navigation service is temporarily unavailable.")


@router.post("/crowd/analyze", response_model=CrowdAnalysisResponse, dependencies=[Depends(_rate_limited)])
async def crowd_endpoint(payload: CrowdAnalysisRequest) -> CrowdAnalysisResponse:
    """
    Real-time crowd-density analysis for stadium control room operators.

    Applies deterministic threshold rules to classify each zone by severity
    (low / medium / high / critical), then uses GenAI to produce a triage
    summary. This endpoint is safe to call with no AI key: thresholds fire
    regardless.

    Args:
        payload: List of zone readings with occupancy percentages and inflow rates.

    Returns:
        CrowdAnalysisResponse with sorted alerts and an operational summary.

    Raises:
        HTTPException: 500 if the crowd service encounters an unexpected error.
    """
    try:
        return await crowd.analyze_crowd(payload)
    except Exception:
        logger.exception("crowd_endpoint failed")
        raise HTTPException(status_code=500, detail="Crowd analysis service is temporarily unavailable.")


@router.post("/accessibility", response_model=AccessibilityResponse, dependencies=[Depends(_rate_limited)])
async def accessibility_endpoint(payload: AccessibilityRequest) -> AccessibilityResponse:
    """
    Accessibility guidance for fans with diverse needs.

    Looks up relevant services from the static resource catalogue, then
    asks GenAI to craft a personalised plain-language response. Falls back
    to a rule-based template if GenAI is unavailable.

    Args:
        payload: Fan's accessibility query, stated needs, and preferred language.

    Returns:
        AccessibilityResponse with guidance text and a list of available resources.

    Raises:
        HTTPException: 500 if the accessibility service encounters an unexpected error.
    """
    try:
        return await accessibility.get_accessibility_guidance(payload)
    except Exception:
        logger.exception("accessibility_endpoint failed")
        raise HTTPException(status_code=500, detail="Accessibility service is temporarily unavailable.")


@router.post("/translate", response_model=TranslateResponse, dependencies=[Depends(_rate_limited)])
async def translate_endpoint(payload: TranslateRequest) -> TranslateResponse:
    """
    Text translation into any of the 10 supported languages.

    Uses Gemini to translate while preserving tone and sports-event context.
    Returns a bracketed offline notice if GenAI is unavailable.

    Args:
        payload: Source text and target language code (e.g. "es", "fr", "ar").

    Returns:
        TranslateResponse with the translated text, target language, and source tag.

    Raises:
        HTTPException: 500 if the translation service encounters an unexpected error.
    """
    try:
        return await assistant.translate(payload)
    except Exception:
        logger.exception("translate_endpoint failed")
        raise HTTPException(status_code=500, detail="Translation service is temporarily unavailable.")


@router.post("/sustainability", response_model=SustainabilityResponse, dependencies=[Depends(_rate_limited)])
async def sustainability_endpoint(payload: SustainabilityRequest) -> SustainabilityResponse:
    """
    Personalised sustainability tips for fans attending the event.

    Generates 3 context-aware tips via GenAI, or returns a curated static
    list if the model is unavailable.

    Args:
        payload: Short context string describing the fan's situation.

    Returns:
        SustainabilityResponse with a list of actionable sustainability tips.

    Raises:
        HTTPException: 500 if the sustainability service encounters an unexpected error.
    """
    try:
        return await assistant.get_sustainability_tips(payload)
    except Exception:
        logger.exception("sustainability_endpoint failed")
        raise HTTPException(status_code=500, detail="Sustainability service is temporarily unavailable.")


@router.post("/emergency", response_model=EmergencyResponse, dependencies=[Depends(_rate_limited)])
async def emergency_endpoint(payload: EmergencyRequest) -> EmergencyResponse:
    """
    Emergency situation decision-support for fans and stewards.

    Keyword-matches the reported situation to determine whether human
    escalation is required, then generates calm step-by-step instructions
    via GenAI. **This endpoint never returns a 500** — a hardcoded human-
    hotline fallback is always returned instead, ensuring safety guidance
    is available even during a complete system outage.

    Args:
        payload: Free-text situation description, optional zone ID, and language.

    Returns:
        EmergencyResponse with instructions, escalation flag, and hotline details.
    """
    try:
        return await assistant.handle_emergency(payload)
    except Exception:
        logger.exception("emergency_endpoint failed")
        # Emergency guidance must NEVER 500 into silence — always give the human-hotline fallback.
        return EmergencyResponse(
            instructions=["Contact the nearest steward or the Stadium Emergency Control Room immediately."],
            escalate_to_human=True,
            hotline="Stadium Emergency Control Room: internal ext. 4444 / radio channel 1",
            source="fallback",
        )


@router.post("/transport", response_model=TransportResponse, dependencies=[Depends(_rate_limited)])
async def transport_endpoint(payload: TransportRequest) -> TransportResponse:
    """
    Transportation and parking recommendations ranked by ETA and availability.

    Aggregates parking-lot occupancy and transit-line data, ranks options
    deterministically, then uses GenAI to produce a concise recommendation
    summary tailored to the fan's party size and time to kickoff.

    Args:
        payload: Preferred mode, party size, accessibility needs, and minutes to kickoff.

    Returns:
        TransportResponse with ranked options, a recommended option ID, and summary.

    Raises:
        HTTPException: 500 if the transport service encounters an unexpected error.
    """
    try:
        return await transport.get_transport_options(payload)
    except Exception:
        logger.exception("transport_endpoint failed")
        raise HTTPException(status_code=500, detail="Transport service is temporarily unavailable.")


@router.get("/health")
async def health() -> dict[str, object]:
    """
    Liveness probe for load balancers and health monitors.

    Returns:
        A dict with ``status`` (always ``"ok"``) and ``genai_available`` boolean.
    """
    return {"status": "ok", "genai_available": is_ai_available()}
