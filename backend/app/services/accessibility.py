"""
Accessibility guidance service for StadiumOS GenAI.

Helps fans with diverse needs find the right services, facilities, and
staff within the venue.  Provides a static catalogue of known resources
and uses Gemini to craft a personalised plain-language response.

Design principles
-----------------
* The static resource list (``_STATIC_RESOURCES``) is the source of truth.
  GenAI is instructed to answer **only from that list** so that no
  non-existent service is ever advertised to a fan.
* The fallback response (``_fallback``) covers the most common need
  patterns and is always available regardless of GenAI connectivity.
"""
from __future__ import annotations

from app.schemas import AccessibilityRequest, AccessibilityResponse
from app.security import sanitize_user_text
from app.services import ai_service

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Maximum tokens requested from the GenAI model for accessibility responses.
_GUIDANCE_MAX_TOKENS: int = 200

#: Static catalogue of accessibility resources available at the venue.
_STATIC_RESOURCES: list[str] = [
    "Accessible Seating Platform — South Concourse, step-free from Gate A/B/D",
    "Sensory Room — quiet, low-light space near the Family Zone for neurodivergent fans",
    "Wheelchair loan desk — Gate A Guest Services, no reservation required",
    "Assistive listening devices — available at any Guest Services desk",
    "Companion/carer free-entry policy — present accessibility documentation at any gate",
]


# ---------------------------------------------------------------------------
# Public service function
# ---------------------------------------------------------------------------

async def get_accessibility_guidance(req: AccessibilityRequest) -> AccessibilityResponse:
    """
    Return personalised accessibility guidance for a fan's stated needs.

    Attempts a GenAI response grounded in the static resource catalogue.
    Falls back to a template-based response when the model is unavailable.

    Args:
        req: Validated accessibility request with a query string, list of
             stated needs, and preferred language.

    Returns:
        AccessibilityResponse with plain-language guidance, the full
        resource catalogue, and a source tag (``"genai"`` or ``"fallback"``).
    """
    reply = await _generate(req)
    source = "genai" if reply else "fallback"
    if not reply:
        reply = _fallback(req)
    return AccessibilityResponse(guidance=reply, resources=_STATIC_RESOURCES, source=source)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fallback(req: AccessibilityRequest) -> str:
    """
    Build a template-based accessibility response without GenAI.

    Mentions the fan's stated needs (if provided), directs them to the
    Accessible Seating Platform and Guest Services desks, and highlights
    teal-armband accessibility stewards.

    Args:
        req: The original accessibility request.

    Returns:
        A human-readable guidance string.
    """
    needs = ", ".join(req.needs) if req.needs else "your accessibility needs"
    return (
        f"For {needs}, the Accessible Seating Platform on the South Concourse is step-free from Gates A, B and D. "
        "Guest Services desks near every gate can arrange a wheelchair escort, assistive listening device, "
        "or sensory-room access on request. Staff wearing a teal armband are trained accessibility stewards."
    )


async def _generate(req: AccessibilityRequest) -> str | None:
    """
    Ask Gemini to answer the fan's accessibility query from the resource catalogue.

    The model is instructed to stay strictly within the provided resource list
    and suggest asking an on-site steward if no resource matches.

    Args:
        req: The validated accessibility request.

    Returns:
        A GenAI-generated guidance string, or ``None`` if the model is unavailable.
    """
    resources_text = "\n".join(f"- {r}" for r in _STATIC_RESOURCES)
    system_prompt = (
        "You are the accessibility concierge for a FIFA World Cup 2026 stadium. Answer the fan's question "
        "using ONLY the resource list provided, in 2-4 plain-language sentences. Never invent a service, "
        "room, or policy that isn't in the list. If nothing in the list matches, say so and suggest asking "
        f"a teal-armband accessibility steward. Respond only in {req.language}."
    )
    user_prompt = (
        f"Fan question: {sanitize_user_text(req.query)}\n"
        f"Stated needs: {', '.join(req.needs) if req.needs else 'none specified'}\n"
        f"Available resources:\n{resources_text}"
    )
    return await ai_service.generate(system_prompt, user_prompt, max_tokens=_GUIDANCE_MAX_TOKENS)
