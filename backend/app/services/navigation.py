"""
Indoor wayfinding service for StadiumOS GenAI.

Computes the shortest walking route between any two zones in the venue's
static graph (:data:`app.data.stadium_map.STADIUM_GRAPH`) using Dijkstra's
algorithm, then asks Gemini to narrate the route in a friendly, fan-facing
style.

Design decisions
----------------
* Crowd levels are simulated from a deterministic pseudo-random seed so
  that demo outputs are stable per zone but vary between zones.  In a
  production deployment this would be replaced by live occupancy data.
* The full routing pipeline (graph lookup → Dijkstra → step building) is
  synchronous and has zero network dependencies, guaranteeing sub-ms
  latency even when GenAI is unavailable.
"""
from __future__ import annotations

import random
from typing import List

from app.data.stadium_map import STADIUM_GRAPH, is_valid_zone, shortest_path, zone_display_name
from app.schemas import NavigationRequest, NavigationResponse, NavigationStep
from app.security import sanitize_user_text
from app.services import ai_service

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Crowd level labels used for simulated zone occupancy.
_CROWD_LEVELS: list[str] = ["low", "moderate", "high"]

#: Maximum tokens requested from the GenAI model for route narratives.
_NARRATIVE_MAX_TOKENS: int = 220

#: Fallback narrative suffix appended when the route is fully accessible.
_ACCESSIBLE_ROUTE_NOTE: str = " This route avoids stairs and uses accessible ramps throughout."


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _simulated_crowd_level(zone_id: str) -> str:
    """
    Return a deterministic, stable crowd level for a given zone identifier.

    The random seed is derived from the zone ID so that demo outputs are
    consistent across calls without requiring a live occupancy feed.

    Args:
        zone_id: The venue zone identifier (e.g. ``"concourse_north"``).

    Returns:
        One of ``"low"``, ``"moderate"``, or ``"high"``.
    """
    random.seed(zone_id)
    return random.choice(_CROWD_LEVELS)


def _build_steps(path: List[str]) -> List[NavigationStep]:
    """
    Convert a list of zone IDs into structured :class:`~app.schemas.NavigationStep` objects.

    Each step represents one edge of the graph (i.e., one segment of the walk),
    annotated with an estimated walking time and a simulated crowd level.

    Args:
        path: Ordered list of zone IDs from origin to destination (inclusive).

    Returns:
        A list of NavigationStep objects, one per graph edge in the path.
    """
    steps: List[NavigationStep] = []
    for i in range(len(path) - 1):
        current, next_zone = path[i], path[i + 1]
        weight = next(w for n, w in STADIUM_GRAPH[current]["neighbors"] if n == next_zone)
        steps.append(
            NavigationStep(
                instruction=f"From {zone_display_name(current)}, proceed to {zone_display_name(next_zone)}.",
                zone=next_zone,
                estimated_minutes=float(weight),
                crowd_level=_simulated_crowd_level(next_zone),
            )
        )
    return steps


def _fallback_narrative(req: NavigationRequest, steps: List[NavigationStep], accessible: bool) -> str:
    """
    Build a plain-text navigation narrative without GenAI.

    Concatenates all step instructions into a single sentence and appends
    an accessibility notice if the route is fully step-free.

    Args:
        req: The original navigation request.
        steps: The list of computed navigation steps.
        accessible: Whether every zone in the path is marked accessible.

    Returns:
        A human-readable narrative string.
    """
    parts = [s.instruction for s in steps]
    note = _ACCESSIBLE_ROUTE_NOTE if accessible and req.accessibility_needs else ""
    return " ".join(parts) + note


# ---------------------------------------------------------------------------
# Public service function
# ---------------------------------------------------------------------------

async def get_navigation(req: NavigationRequest) -> NavigationResponse:
    """
    Compute and narrate the optimal indoor route between two venue zones.

    Normalises origin and destination identifiers, runs Dijkstra on the
    static stadium graph (respecting accessibility constraints), builds
    structured step objects, and then requests a fan-friendly narrative from
    Gemini.

    Args:
        req: Validated navigation request with origin, destination, accessibility
             needs, and preferred language.

    Returns:
        NavigationResponse with structured steps, total walking time, a
        narrative description, an accessibility flag, and a source tag.
        If the origin or destination cannot be found, or no accessible route
        exists, an explanatory fallback response is returned.
    """
    origin = req.origin.strip().lower().replace(" ", "_")
    destination = req.destination.strip().lower().replace(" ", "_")

    if not is_valid_zone(origin) or not is_valid_zone(destination):
        return NavigationResponse(
            steps=[], total_minutes=0, accessible=False, source="fallback",
            narrative=(
                f"I couldn't find a match for '{req.origin}' or '{req.destination}' on the venue map. "
                "Try a gate name (Gate A/B/C), a section range (e.g. '101-120'), or a landmark "
                "like 'Family Zone', 'Medical Station' or 'Accessible Seating'."
            ),
        )

    avoid: List[str] = []
    if req.accessibility_needs and "wheelchair" in [n.lower() for n in req.accessibility_needs]:
        avoid = [z for z, meta in STADIUM_GRAPH.items() if not meta["accessible"]]

    path, total_minutes = shortest_path(origin, destination, avoid_zones=avoid)
    if not path:
        return NavigationResponse(
            steps=[], total_minutes=0, accessible=False, source="fallback",
            narrative=(
                "No accessible route was found between those two points. "
                "Please ask a nearby steward for assisted routing."
            ),
        )

    steps = _build_steps(path)
    accessible = all(STADIUM_GRAPH[z]["accessible"] for z in path)

    narrative = await _generate_narrative(req, path, steps, accessible)
    source = "genai" if narrative else "fallback"
    if not narrative:
        narrative = _fallback_narrative(req, steps, accessible)

    return NavigationResponse(
        steps=steps, total_minutes=total_minutes, narrative=narrative,
        accessible=accessible, source=source,
    )


async def _generate_narrative(
    req: NavigationRequest,
    path: List[str],
    steps: List[NavigationStep],
    accessible: bool,
) -> str | None:
    """
    Ask Gemini to narrate the route steps as a fan-facing wayfinding message.

    Args:
        req: The original navigation request (used for language and accessibility flags).
        path: Ordered list of zone IDs (used internally; not directly sent to the model).
        steps: Structured step objects whose instructions are sent as context.
        accessible: Whether the route is fully step-free.

    Returns:
        A natural-language narrative string, or ``None`` if GenAI is unavailable.
    """
    system_prompt = (
        "You are the wayfinding assistant for a FIFA World Cup 2026 host stadium. "
        "Turn a list of routing steps into 2-4 short, friendly, encouraging sentences "
        "a fan can follow while walking. Mention crowd levels only if 'high'. "
        "If the fan requested accessibility support, reassure them the route avoids stairs. "
        f"Respond only in {req.language}. Do not invent landmarks not present in the steps."
    )
    steps_text = "\n".join(
        f"- {s.instruction} (~{s.estimated_minutes} min, crowd: {s.crowd_level})" for s in steps
    )
    user_prompt = (
        f"Route steps:\n{sanitize_user_text(steps_text)}\n"
        f"Accessibility requested: {bool(req.accessibility_needs)}\n"
        f"Route is fully accessible: {accessible}"
    )
    return await ai_service.generate(system_prompt, user_prompt, max_tokens=_NARRATIVE_MAX_TOKENS)
