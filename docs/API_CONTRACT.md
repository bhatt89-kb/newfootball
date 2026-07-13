# API Contract Documentation

This document defines the public API contract for StadiumOS GenAI. All endpoints follow RESTful principles and return JSON responses.

## Base URL

- **Development**: `http://localhost:8000`
- **Production**: `https://your-domain.com`

All API endpoints are versioned under `/api/v1`.

## Authentication

Most endpoints are public. Admin endpoints require the `X-Admin-Key` header:

```http
X-Admin-Key: your-admin-api-key
```

## Common Response Format

All responses include a `source` field indicating whether the response came from GenAI or deterministic fallback:

```json
{
  "source": "genai" | "fallback",
  "...": "endpoint-specific fields"
}
```

## Endpoints

### 1. Health Check

**GET** `/api/v1/health`

Check service health and GenAI availability.

**Parameters**: None

**Response**: `200 OK`

```json
{
  "status": "healthy",
  "genai_available": true
}
```

**Example**:

```bash
curl http://localhost:8000/api/v1/health
```

---

### 2. Chat Assistant

**POST** `/api/v1/chat`

Multilingual fan/staff assistant with role-aware responses.

**Request Body**:

```json
{
  "message": "Where is gate 5?",
  "language": "en",
  "user_role": "fan"
}
```

**Parameters**:

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `message` | string | Yes | 1-500 chars | User's question or statement |
| `language` | string | Yes | ISO 639-1 code | One of: `en`, `es`, `fr`, `de`, `it`, `pt`, `zh`, `ja`, `ar`, `hi` |
| `user_role` | string | Yes | enum | One of: `fan`, `volunteer`, `staff`, `organizer` |

**Response**: `200 OK`

```json
{
  "reply": "Gate 5 is located on the north side of the stadium, near Section 101. Follow the signs for 'North Entrance' from the main plaza.",
  "suggested_action": "navigate",
  "confidence": "high",
  "source": "genai",
  "language": "en"
}
```

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `reply` | string | Assistant's response message |
| `suggested_action` | string? | Optional action hint: `navigate`, `crowd`, `transport`, `accessibility`, `emergency` |
| `confidence` | string | Response confidence: `high`, `medium`, `low` |
| `source` | string | Response source: `genai` or `fallback` |
| `language` | string | Language of the response |

**Error Responses**:

- `422 Unprocessable Entity`: Invalid input (unsupported language, missing fields, oversized message)
- `500 Internal Server Error`: Service exception (fallback response still returned)

---

### 3. Navigation

**POST** `/api/v1/navigate`

Turn-by-turn wayfinding with accessibility support.

**Request Body**:

```json
{
  "origin": "main_entrance",
  "destination": "section_220",
  "accessibility_needs": ["wheelchair"]
}
```

**Parameters**:

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `origin` | string | Yes | 1-50 chars | Starting location zone ID |
| `destination` | string | Yes | 1-50 chars | Target location zone ID |
| `accessibility_needs` | array[string] | No | Max 5 items | Needs: `wheelchair`, `visual`, `hearing`, `mobility` |

**Response**: `200 OK`

```json
{
  "steps": [
    {
      "instruction": "From Main Entrance, proceed straight ahead",
      "distance_meters": 50,
      "zone": "main_concourse"
    },
    {
      "instruction": "Turn right at the central plaza",
      "distance_meters": 30,
      "zone": "plaza_north"
    },
    {
      "instruction": "Take the accessible ramp up to Level 2",
      "distance_meters": 20,
      "zone": "ramp_north_2"
    },
    {
      "instruction": "You have arrived at Section 220",
      "distance_meters": 0,
      "zone": "section_220"
    }
  ],
  "total_distance_meters": 100,
  "estimated_time_minutes": 4,
  "accessibility_verified": true,
  "narrative": "Your accessible route to Section 220 is ready. Head straight from the Main Entrance, turn right at the plaza, and take the ramp to Level 2. The total distance is about 100 meters.",
  "source": "genai"
}
```

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `steps` | array[object] | Turn-by-turn navigation steps |
| `steps[].instruction` | string | Human-readable instruction |
| `steps[].distance_meters` | number | Distance to next step |
| `steps[].zone` | string | Zone ID for this step |
| `total_distance_meters` | number | Total route distance |
| `estimated_time_minutes` | number | Estimated walking time |
| `accessibility_verified` | boolean | Route meets accessibility requirements |
| `narrative` | string | Natural language route summary |
| `source` | string | Response source |

**Special Cases**:

- If origin/destination is invalid: Returns helpful message, not an error
- If no accessible route exists: Returns alternative suggestion
- If route includes stairs: Marks `accessibility_verified: false`

---

### 4. Crowd Analysis

**POST** `/api/v1/crowd/analyze`

Crowd safety monitoring and operator briefing.

**Request Body**:

```json
{
  "zones": [
    {"zone_id": "gate_a", "occupancy": 45, "capacity": 200},
    {"zone_id": "concourse_1", "occupancy": 850, "capacity": 1000},
    {"zone_id": "section_101", "occupancy": 5800, "capacity": 6000}
  ]
}
```

**Parameters**:

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `zones` | array[object] | Yes | 1-50 zones | Zone occupancy data |
| `zones[].zone_id` | string | Yes | 1-50 chars | Zone identifier |
| `zones[].occupancy` | number | Yes | 0-1000000 | Current occupancy count |
| `zones[].capacity` | number | Yes | 1-1000000 | Maximum capacity |

**Response**: `200 OK`

```json
{
  "overall_severity": "medium",
  "alerts": [
    {
      "zone_id": "section_101",
      "severity": "high",
      "occupancy_percent": 96.7,
      "message": "Section 101 is at 97% capacity (high)"
    },
    {
      "zone_id": "concourse_1",
      "severity": "medium",
      "occupancy_percent": 85.0,
      "message": "Concourse 1 is at 85% capacity (medium)"
    }
  ],
  "operator_briefing": "Section 101 is critically full at 97% capacity—consider diverting new arrivals. Concourse 1 is approaching threshold at 85%.",
  "source": "genai"
}
```

**Severity Thresholds**:

| Severity | Threshold | Color Code |
|----------|-----------|------------|
| None | 0-69% | Green |
| Medium | 70-84% | Yellow |
| High | 85-94% | Orange |
| Critical | 95-100% | Red |

---

### 5. Transport Recommendations

**POST** `/api/v1/transport`

Parking, shuttle, and transit recommendations.

**Request Body**:

```json
{
  "mode": "any",
  "party_size": 4,
  "accessibility_needs": []
}
```

**Parameters**:

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `mode` | string | Yes | enum | Transport mode: `any`, `car`, `transit`, `shuttle` |
| `party_size` | number | Yes | 1-100 | Number of people |
| `accessibility_needs` | array[string] | No | Max 5 items | Same as navigation endpoint |

**Response**: `200 OK`

```json
{
  "recommendations": [
    {
      "name": "North Parking Lot",
      "type": "parking",
      "available_spaces": 120,
      "occupancy_percent": 40,
      "distance_to_venue_meters": 200,
      "accessible": true,
      "estimated_cost_usd": 20
    },
    {
      "name": "Metro Line 3",
      "type": "transit",
      "next_departure_minutes": 5,
      "frequency_minutes": 10,
      "accessible": true,
      "estimated_cost_usd": 3
    }
  ],
  "summary": "Best option for 4 people: North Parking Lot has plenty of space (40% full) and is just 200 meters from the venue. Alternative: Metro Line 3 departs in 5 minutes.",
  "source": "genai"
}
```

---

### 6. Accessibility Concierge

**POST** `/api/v1/accessibility`

Accessibility guidance and resource information.

**Request Body**:

```json
{
  "need_type": "wheelchair",
  "question": "Are there accessible restrooms near Section 105?"
}
```

**Parameters**:

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `need_type` | string | Yes | enum | One of: `wheelchair`, `visual`, `hearing`, `sensory`, `mobility`, `general` |
| `question` | string | Yes | 1-500 chars | Specific accessibility question |

**Response**: `200 OK`

```json
{
  "resources": [
    {
      "title": "Accessible Restrooms - Level 1",
      "description": "Wheelchair-accessible restrooms are located near Gates 4, 8, and 12 on Level 1",
      "location": "Level 1, multiple locations",
      "contact": null
    }
  ],
  "guidance": "Yes, there are accessible restrooms on Level 1 near Section 105. The closest one is at Gate 4, which is approximately 50 meters from your section.",
  "source": "genai"
}
```

---

### 7. Translation

**POST** `/api/v1/translate`

Free-text translation service.

**Request Body**:

```json
{
  "text": "Where is the nearest restroom?",
  "source_language": "en",
  "target_language": "es"
}
```

**Response**: `200 OK`

```json
{
  "translated_text": "¿Dónde está el baño más cercano?",
  "source_language": "en",
  "target_language": "es",
  "source": "genai"
}
```

**Fallback Behavior**: If GenAI unavailable, returns original text with label:

```json
{
  "translated_text": "[Translation unavailable] Where is the nearest restroom?",
  "source_language": "en",
  "target_language": "es",
  "source": "fallback"
}
```

---

### 8. Sustainability Tips

**POST** `/api/v1/sustainability`

Personalized sustainability guidance.

**Request Body**:

```json
{
  "context": "fan",
  "interest": "waste_reduction"
}
```

**Response**: `200 OK`

```json
{
  "tips": [
    "Bring a reusable water bottle—refill stations are available at every level",
    "Use the stadium's recycling bins (blue for recyclables, green for compost)",
    "Consider taking public transit to reduce your carbon footprint"
  ],
  "impact_message": "If every fan followed these tips, we'd reduce waste by 60% per match.",
  "source": "genai"
}
```

---

### 9. Emergency Decision Support

**POST** `/api/v1/emergency`

Real-time safety decision support with mandatory human escalation.

**Request Body**:

```json
{
  "situation": "medical emergency in section 203",
  "severity": "high",
  "language": "en"
}
```

**Response**: `200 OK`

```json
{
  "immediate_actions": [
    "Call emergency medical services immediately (911)",
    "Alert stadium medical team via radio channel 5",
    "Clear a path to the affected section",
    "Prepare for medical team arrival"
  ],
  "escalate_to_human": true,
  "escalation_reason": "medical",
  "guidance": "This is a medical emergency. Contact emergency services immediately and alert the stadium medical team. Clear access routes to Section 203.",
  "source": "genai",
  "language": "en"
}
```

**Critical Safety Rule**: `escalate_to_human` is ALWAYS `true` for keywords: `medical`, `fire`, `evacuation`, `injury`, `threat`, `violence`.

---

### 10. Admin Status

**GET** `/admin/status`

**Authentication**: Requires `X-Admin-Key` header

Operator-only deployment status check.

**Response**: `200 OK`

```json
{
  "app_name": "StadiumOS GenAI",
  "environment": "production",
  "genai_available": true,
  "cache_available": true,
  "cache_stats": {
    "available": true,
    "keys": 1247,
    "total_commands_processed": 45893,
    "keyspace_hits": 37612,
    "keyspace_misses": 8281,
    "hit_rate": 81.94
  },
  "rate_limit": "30 req / 60s"
}
```

---

### 11. Cache Management

**GET** `/admin/cache/stats`

**Authentication**: Requires `X-Admin-Key` header

Detailed cache statistics.

**POST** `/admin/cache/flush`

**Authentication**: Requires `X-Admin-Key` header

Flush cache entries matching pattern.

**Query Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pattern` | string | `*` | Redis key pattern to flush |

**Example**:

```bash
curl -X POST "http://localhost:8000/admin/cache/flush?pattern=ai_response:*" \
  -H "X-Admin-Key: your-key"
```

---

## Error Handling

### Standard Error Response

```json
{
  "detail": "Error message describing what went wrong"
}
```

### HTTP Status Codes

| Code | Meaning | Usage |
|------|---------|-------|
| `200` | OK | Successful request |
| `401` | Unauthorized | Missing or invalid admin key |
| `422` | Unprocessable Entity | Invalid request payload |
| `500` | Internal Server Error | Service exception (graceful fallback provided when possible) |

### Validation Errors

```json
{
  "detail": [
    {
      "type": "string_too_long",
      "loc": ["body", "message"],
      "msg": "String should have at most 500 characters",
      "input": "very long message...",
      "ctx": {"max_length": 500}
    }
  ]
}
```

---

## Rate Limiting

- **Default**: 30 requests per 60 seconds per IP address
- **Admin endpoints**: No rate limiting (but require authentication)
- **Response header**: `X-RateLimit-Remaining` indicates remaining requests

When rate limit is exceeded:

```json
{
  "detail": "Rate limit exceeded. Please try again later."
}
```

---

## Versioning

The API is versioned via the URL path (`/api/v1`). Breaking changes will increment the major version (`/api/v2`).

**Current version**: `v1`

**Backward compatibility policy**: Minor updates (new fields, new optional parameters) will not change the version. Breaking changes (removed fields, changed response structure) will require a new version.

---

## Interactive Documentation

Explore the API interactively:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

---

## SDK Examples

### Python (using `httpx`)

```python
import httpx

async def get_navigation(origin: str, destination: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/navigate",
            json={
                "origin": origin,
                "destination": destination,
                "accessibility_needs": []
            }
        )
        return response.json()
```

### JavaScript (using `fetch`)

```javascript
async function getChatResponse(message, language = 'en') {
  const response = await fetch('http://localhost:8000/api/v1/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      language,
      user_role: 'fan'
    })
  });
  return response.json();
}
```

### cURL

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Chat request
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Where is gate 5?",
    "language": "en",
    "user_role": "fan"
  }'

# Admin status (requires key)
curl http://localhost:8000/admin/status \
  -H "X-Admin-Key: your-admin-key"
```

---

## Testing Recommendations

1. **Functional Tests**: Verify each endpoint returns expected structure
2. **Fallback Tests**: Test with GenAI disabled (`GOOGLE_API_KEY` unset)
3. **Validation Tests**: Send invalid payloads to verify error handling
4. **Load Tests**: Ensure rate limiting works correctly
5. **Security Tests**: Verify admin endpoints reject missing/wrong keys

---

## Changelog

See `CHANGELOG.md` for API changes between versions.

---

## Support

- **Documentation**: `docs/`
- **Issues**: GitHub Issues
- **OpenAPI Spec**: `/openapi.json`
