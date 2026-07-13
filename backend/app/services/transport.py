"""
Transportation and parking recommendation service for StadiumOS GenAI.

Aggregates parking-lot occupancy data and transit/shuttle line information,
ranks options deterministically by availability and ETA, and then uses Gemini
to produce a concise fan-facing recommendation summary.

Architecture
------------
* **Deterministic layer** (``_car_options``, ``_transit_options``, ``_rank``):
  Pure functions with no network dependencies.  They always return a correct,
  ranked result even during a complete GenAI or Redis outage.
* **AI narrative layer** (``_generate_summary``): Optional enrichment that
  adds a warm, contextual recommendation sentence.  Falls back to the
  rule-based ``_fallback_summary`` if the model is unavailable.

Thresholds
----------
Parking-lot status thresholds are named constants so that operational
policy changes require only a single-line edit in this file.
"""
from __future__ import annotations

import logging
from typing import List

from app.data.stadium_map import zone_display_name
from app.data.transit import (
    PARKING_LOTS,
    TRANSIT_LINES,
    accessible_spaces_available,
    parking_occupancy_percent,
)
from app.schemas import TransportOption, TransportRequest, TransportResponse
from app.security import sanitize_user_text
from app.services import ai_service

logger = logging.getLogger("stadiumos.transport")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Occupancy percentage at or above which a parking lot is marked "full".
_LOT_FULL_THRESHOLD: float = 98.0

#: Occupancy percentage at or above which a parking lot is marked "near_full".
_LOT_NEAR_FULL_THRESHOLD: float = 90.0

#: Statuses that cause an option to be sorted to the bottom of the ranked list.
_BAD_STATUSES: frozenset[str] = frozenset({"full", "suspended"})

#: Accessibility-related need keywords that trigger accessible-only filtering.
_ACCESSIBLE_NEEDS_KEYWORDS: frozenset[str] = frozenset({"wheelchair", "mobility", "accessible"})

#: Maximum number of transport options passed to the GenAI summary prompt.
_MAX_OPTIONS_IN_PROMPT: int = 5

#: Maximum tokens requested from the GenAI model for transport summaries.
_SUMMARY_MAX_TOKENS: int = 150


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _car_options(req: TransportRequest, needs_accessible: bool) -> List[TransportOption]:
    """
    Build a list of parking-lot transport options from the static dataset.

    Filters out lots with no accessible spaces when ``needs_accessible`` is
    ``True``.  Computes status by comparing occupancy against named thresholds.

    Args:
        req: The original transport request (retained for future use by extensions).
        needs_accessible: Whether the fan requires an accessible parking space.

    Returns:
        A list of TransportOption objects, one per qualifying parking lot.
    """
    options: List[TransportOption] = []
    for lot_id, lot in PARKING_LOTS.items():
        occupancy = parking_occupancy_percent(lot_id)
        free_accessible = accessible_spaces_available(lot_id)

        if needs_accessible and free_accessible <= 0:
            continue  # No accessible spaces left at this lot — do not recommend it.

        if occupancy >= _LOT_FULL_THRESHOLD:
            status = "full"
        elif occupancy >= _LOT_NEAR_FULL_THRESHOLD:
            status = "near_full"
        else:
            status = "available"

        detail = (
            f"{occupancy:.0f}% full, {lot['walk_minutes_to_gate']} min walk to "
            f"{zone_display_name(lot['nearest_gate'])}."
        )
        if needs_accessible:
            detail += f" {free_accessible} accessible space(s) free."

        options.append(
            TransportOption(
                option_id=lot_id,
                mode="car",
                name=lot["name"],
                detail=detail,
                eta_minutes=float(lot["walk_minutes_to_gate"]),
                accessible=free_accessible > 0,
                status=status,
            )
        )
    return options


def _transit_options(
    req: TransportRequest,
    needs_accessible: bool,
    mode_filter: str | None,
) -> List[TransportOption]:
    """
    Build a list of shuttle or public-transit transport options.

    Filters by mode (shuttle / transit) and accessibility if required.
    ETA is estimated as average wait time (half the headway) plus walk time.

    Args:
        req: The original transport request (retained for future use by extensions).
        needs_accessible: Whether the fan requires an accessible vehicle/service.
        mode_filter: If provided, restricts results to this mode (``"shuttle"`` or
                     ``"transit"``).  Pass ``None`` to include all modes.

    Returns:
        A list of TransportOption objects, one per qualifying transit line.
    """
    options: List[TransportOption] = []
    for line_id, line in TRANSIT_LINES.items():
        if mode_filter and line["mode"] != mode_filter:
            continue
        if needs_accessible and not line["accessible"]:
            continue

        avg_wait = line["frequency_minutes"] / 2
        eta = avg_wait + line["walk_minutes_to_gate"]
        detail = (
            f"Every {line['frequency_minutes']} min from {line['pickup_point']}, "
            f"{line['walk_minutes_to_gate']} min walk to {zone_display_name(line['nearest_gate'])}."
        )
        options.append(
            TransportOption(
                option_id=line_id,
                mode=line["mode"],
                name=line["name"],
                detail=detail,
                eta_minutes=round(eta, 1),
                accessible=line["accessible"],
                status=line["status"],
            )
        )
    return options


def _rank(options: List[TransportOption]) -> List[TransportOption]:
    """
    Sort transport options so that the best choice appears first.

    Options with a bad status (``"full"`` or ``"suspended"``) are always
    demoted to the bottom of the list.  Among remaining options, the one
    with the lowest ETA ranks highest.  This deterministic ordering is never
    overridden by the GenAI layer.

    Args:
        options: Unordered list of transport options.

    Returns:
        A new list sorted by (is_bad_status, eta_minutes) ascending.
    """
    def sort_key(opt: TransportOption) -> tuple[int, float]:
        return (1 if opt.status in _BAD_STATUSES else 0, opt.eta_minutes)

    return sorted(options, key=sort_key)


def _fallback_summary(options: List[TransportOption], needs_accessible: bool) -> str:
    """
    Build a plain-text transport summary without GenAI.

    Args:
        options: Ranked list of transport options (best first).
        needs_accessible: Whether the fan requires accessible transport.

    Returns:
        A concise, human-readable summary string.
    """
    if not options:
        if needs_accessible:
            return "No accessible transport options currently match your needs. Please check with Guest Services."
        return "No transport options currently match your filters."
    best = options[0]
    if best.status in _BAD_STATUSES:
        return f"All matching options are currently constrained; the least-delayed is {best.name}."
    return f"Best option: {best.name} — {best.detail}"


# ---------------------------------------------------------------------------
# Public service function
# ---------------------------------------------------------------------------

async def get_transport_options(req: TransportRequest) -> TransportResponse:
    """
    Aggregate, rank, and summarise transport options for a fan.

    Collects parking and transit options based on the requested mode,
    filters by accessibility if required, ranks them deterministically,
    and requests a GenAI-generated recommendation summary.

    Args:
        req: Validated transport request including mode preference, party size,
             accessibility needs, and minutes to kickoff.

    Returns:
        TransportResponse with a ranked list of options, the recommended option
        ID (top-ranked), a summary string, and a source tag.
    """
    needs_accessible = any(
        n.lower() in _ACCESSIBLE_NEEDS_KEYWORDS for n in req.accessibility_needs
    )

    options: List[TransportOption] = []
    if req.mode in (None, "car"):
        options += _car_options(req, needs_accessible)
    if req.mode in (None, "shuttle"):
        options += _transit_options(req, needs_accessible, "shuttle")
    if req.mode in (None, "transit"):
        options += _transit_options(req, needs_accessible, "transit")

    options = _rank(options)
    recommended_id = options[0].option_id if options else None

    summary = await _generate_summary(req, options, needs_accessible)
    source = "genai" if summary else "fallback"
    if not summary:
        summary = _fallback_summary(options, needs_accessible)

    return TransportResponse(
        options=options,
        recommended_option_id=recommended_id,
        summary=summary,
        source=source,
    )


async def _generate_summary(
    req: TransportRequest,
    options: List[TransportOption],
    needs_accessible: bool,
) -> str | None:
    """
    Ask Gemini for a one- or two-sentence transport recommendation.

    Only the top :data:`_MAX_OPTIONS_IN_PROMPT` options are sent to the
    model to keep prompt size bounded.

    Args:
        req: The original transport request (used for language and context fields).
        options: Ranked list of transport options (best first).
        needs_accessible: Whether the fan requires accessible transport.

    Returns:
        A GenAI-generated recommendation string, or ``None`` if there are no
        options or if GenAI is unavailable.
    """
    if not options:
        return None
    system_prompt = (
        "You are 'Ana', a transport-advisory assistant for FIFA World Cup 2026 stadium fans. Given a "
        "ranked list of parking, shuttle, and transit options, recommend the single best one in one tight "
        "sentence (max 35 words), then optionally one short backup sentence. Be concrete, warm, and "
        "practical. Never invent an option that isn't in the list. Respond only in "
        f"{req.language}."
    )
    options_text = "\n".join(
        f"- [{o.mode}] {o.name}: {o.detail} (status: {o.status}, ETA {o.eta_minutes:.0f} min)"
        for o in options[:_MAX_OPTIONS_IN_PROMPT]
    )
    context_bits = [f"Party size: {req.party_size}"]
    if req.minutes_to_kickoff is not None:
        context_bits.append(f"Minutes to kickoff: {req.minutes_to_kickoff}")
    if needs_accessible:
        context_bits.append("Requires wheelchair-accessible option")
    user_prompt = (
        f"{sanitize_user_text(', '.join(context_bits))}\nRanked options:\n{sanitize_user_text(options_text)}"
    )
    return await ai_service.generate(system_prompt, user_prompt, max_tokens=_SUMMARY_MAX_TOKENS)
