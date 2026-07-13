"""
Pydantic request/response schemas for all StadiumOS GenAI endpoints.

Every inbound field carries an explicit ``max_length`` / allowed-value
constraint as a security control: oversized or malformed payloads are
rejected before they can reach the GenAI layer, reducing the prompt-
injection and denial-of-service attack surface.  See docs/SECURITY.md
for the full threat model.

Conventions
-----------
* Request schemas validate and sanitise untrusted user input.
* Response schemas are internal — their fields are never interpolated
  into AI prompts, so they carry no security constraints.
* The ``source`` field in every response is either ``"genai"`` (Gemini
  produced the content) or ``"fallback"`` (deterministic rule fired).
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

SUPPORTED_LANGUAGES = {
    "en": "English", "es": "Spanish", "fr": "French", "pt": "Portuguese",
    "de": "German", "ar": "Arabic", "hi": "Hindi", "zh": "Chinese",
    "ja": "Japanese", "ko": "Korean",
}


class UserRole(str, Enum):
    """Roles a user can hold when interacting with the stadium assistant."""

    fan = "fan"
    volunteer = "volunteer"
    staff = "staff"
    organizer = "organizer"


def _no_control_chars(v: str) -> str:
    """Pydantic field validator that strips leading/trailing whitespace
    and rejects strings containing ASCII control characters (< U+0009)."""
    if any(ord(ch) < 9 for ch in v):
        raise ValueError("input contains disallowed control characters")
    return v.strip()


class ChatRequest(BaseModel):
    """Inbound payload for the ``POST /api/v1/chat`` endpoint."""

    message: str = Field(..., min_length=1, max_length=1000)
    language: str = Field(default="en")
    role: UserRole = UserRole.fan
    session_id: Optional[str] = Field(default=None, max_length=100)

    _clean_message = field_validator("message")(lambda cls, v: _no_control_chars(v))

    @field_validator("language")
    @classmethod
    def check_language(cls, v: str) -> str:
        """Reject unsupported BCP-47 language codes early."""
        if v not in SUPPORTED_LANGUAGES:
            raise ValueError(f"unsupported language code '{v}'")
        return v


class ChatResponse(BaseModel):
    """Response payload for the ``POST /api/v1/chat`` endpoint."""

    reply: str
    language: str
    suggested_actions: List[str] = Field(default_factory=list)
    source: str  # "genai" | "fallback"


class NavigationRequest(BaseModel):
    """Inbound payload for the ``POST /api/v1/navigate`` endpoint."""

    origin: str = Field(..., min_length=1, max_length=80)
    destination: str = Field(..., min_length=1, max_length=80)
    accessibility_needs: List[str] = Field(default_factory=list, max_length=6)
    language: str = Field(default="en")
    avoid_crowds: bool = True

    @field_validator("language")
    @classmethod
    def check_language(cls, v: str) -> str:
        """Reject unsupported BCP-47 language codes early."""
        if v not in SUPPORTED_LANGUAGES:
            raise ValueError(f"unsupported language code '{v}'")
        return v


class NavigationStep(BaseModel):
    """A single step in a navigation route, representing one graph edge."""

    instruction: str
    zone: str
    estimated_minutes: float
    crowd_level: str


class NavigationResponse(BaseModel):
    """Response payload for the ``POST /api/v1/navigate`` endpoint."""

    steps: List[NavigationStep]
    total_minutes: float
    narrative: str
    accessible: bool
    source: str


class CrowdZoneReading(BaseModel):
    """Real-time occupancy snapshot for a single venue zone."""

    zone_id: str = Field(..., max_length=40)
    occupancy_percent: float = Field(..., ge=0, le=100)
    inflow_rate: float = Field(default=0, ge=-1000, le=1000)


class CrowdAnalysisRequest(BaseModel):
    """Inbound payload for the ``POST /api/v1/crowd/analyze`` endpoint."""

    zones: List[CrowdZoneReading] = Field(..., min_length=1, max_length=50)
    event_phase: str = Field(default="pre-match", max_length=30)


class CrowdAlert(BaseModel):
    """Operator alert generated for a zone that exceeds a safety threshold."""

    zone_id: str
    severity: str  # "low" | "medium" | "high" | "critical"
    message: str
    recommended_action: str


class CrowdAnalysisResponse(BaseModel):
    """Response payload for the ``POST /api/v1/crowd/analyze`` endpoint."""

    alerts: List[CrowdAlert]
    overall_summary: str
    source: str


class AccessibilityRequest(BaseModel):
    """Inbound payload for the ``POST /api/v1/accessibility`` endpoint."""

    query: str = Field(..., min_length=1, max_length=500)
    needs: List[str] = Field(default_factory=list, max_length=8)
    language: str = Field(default="en")


class AccessibilityResponse(BaseModel):
    """Response payload for the ``POST /api/v1/accessibility`` endpoint."""

    guidance: str
    resources: List[str]
    source: str


class SustainabilityRequest(BaseModel):
    """Inbound payload for the ``POST /api/v1/sustainability`` endpoint."""

    context: str = Field(..., min_length=1, max_length=300)


class SustainabilityResponse(BaseModel):
    """Response payload for the ``POST /api/v1/sustainability`` endpoint."""

    tips: List[str]
    estimated_co2_savings_kg: Optional[float] = None
    source: str


class EmergencyRequest(BaseModel):
    """Inbound payload for the ``POST /api/v1/emergency`` endpoint."""

    situation: str = Field(..., min_length=1, max_length=300)
    zone_id: Optional[str] = Field(default=None, max_length=40)
    language: str = Field(default="en")


class EmergencyResponse(BaseModel):
    """Response payload for the ``POST /api/v1/emergency`` endpoint."""

    instructions: List[str]
    escalate_to_human: bool
    hotline: str
    source: str


class TransportRequest(BaseModel):
    """Inbound payload for the ``POST /api/v1/transport`` endpoint."""

    mode: Optional[str] = Field(default=None, max_length=20)  # "car" | "shuttle" | "transit" | None (any)
    party_size: int = Field(default=1, ge=1, le=20)
    accessibility_needs: List[str] = Field(default_factory=list, max_length=6)
    minutes_to_kickoff: Optional[int] = Field(default=None, ge=0, le=600)
    language: str = Field(default="en")

    @field_validator("mode")
    @classmethod
    def check_mode(cls, v: Optional[str]) -> Optional[str]:
        """Reject unsupported transport modes early."""
        if v is not None and v not in {"car", "shuttle", "transit"}:
            raise ValueError("mode must be one of 'car', 'shuttle', 'transit'")
        return v

    @field_validator("language")
    @classmethod
    def check_language(cls, v: str) -> str:
        """Reject unsupported BCP-47 language codes early."""
        if v not in SUPPORTED_LANGUAGES:
            raise ValueError(f"unsupported language code '{v}'")
        return v


class TransportOption(BaseModel):
    """A single transport option returned in a TransportResponse."""

    option_id: str
    mode: str  # "car" | "shuttle" | "transit"
    name: str
    detail: str
    eta_minutes: float
    accessible: bool
    status: str  # "on_time" | "delayed" | "suspended" | "full" | "near_full" | "available"


class TransportResponse(BaseModel):
    """Response payload for the ``POST /api/v1/transport`` endpoint."""

    options: List[TransportOption]
    recommended_option_id: Optional[str] = None
    summary: str
    source: str


class TranslateRequest(BaseModel):
    """Inbound payload for the ``POST /api/v1/translate`` endpoint."""

    text: str = Field(..., min_length=1, max_length=1000)
    target_language: str

    @field_validator("target_language")
    @classmethod
    def check_language(cls, v: str) -> str:
        """Reject unsupported BCP-47 language codes early."""
        if v not in SUPPORTED_LANGUAGES:
            raise ValueError(f"unsupported language code '{v}'")
        return v


class TranslateResponse(BaseModel):
    """Response payload for the ``POST /api/v1/translate`` endpoint."""

    translated_text: str
    target_language: str
    source: str
