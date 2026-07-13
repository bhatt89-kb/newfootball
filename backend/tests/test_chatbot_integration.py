"""
Integration tests for chatbot response variability and multilingual behaviour.

These tests verify that the chatbot produces contextually appropriate responses
for different inputs, roles, and languages when GenAI is available, and that
the fallback mode provides sensible degraded-mode replies.

Test classes
------------
* :class:`TestResponseVariability`   — Different inputs produce different outputs.
* :class:`TestMultilingualBehaviour` — Language codes are honoured in responses.
* :class:`TestFallbackMode`          — Fallback returns reasonable replies with no GenAI.
"""
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def transport():
    """Return an ASGI transport bound to the FastAPI app under test."""
    return ASGITransport(app=app)


# ---------------------------------------------------------------------------
# Response variability tests
# ---------------------------------------------------------------------------

class TestResponseVariability:
    """Verify that different inputs produce meaningfully different responses."""

    @pytest.mark.asyncio
    async def test_different_greetings_produce_different_responses(self, transport):
        """
        Verify that 'hi' and 'hello' don't produce identical GenAI responses.

        Both messages should return HTTP 200 with a non-empty reply.  When GenAI
        is active the replies are expected to differ in phrasing.
        """
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r1 = await client.post("/api/v1/chat", json={"message": "hi",    "language": "en", "user_role": "fan"})
            r2 = await client.post("/api/v1/chat", json={"message": "hello", "language": "en", "user_role": "fan"})

        assert r1.status_code == 200
        assert r2.status_code == 200
        d1, d2 = r1.json(), r2.json()
        assert len(d1["reply"]) > 0
        assert len(d2["reply"]) > 0
        if d1["source"] == "genai" and d2["source"] == "genai":
            assert d1["reply"] != d2["reply"], "GenAI should produce varied responses for similar inputs"

    @pytest.mark.asyncio
    async def test_question_vs_statement_differ(self, transport):
        """
        A question and a statement about the same topic should yield different styles.

        The question form typically gets a direct answer; the statement form may
        receive a more empathetic response.
        """
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r1 = await client.post("/api/v1/chat", json={"message": "Where is gate 5?",     "language": "en", "user_role": "fan"})
            r2 = await client.post("/api/v1/chat", json={"message": "I can't find gate 5",  "language": "en", "user_role": "fan"})

        assert r1.status_code == 200
        assert r2.status_code == 200
        d1, d2 = r1.json(), r2.json()
        assert "reply" in d1 and "reply" in d2
        if d1["source"] == "genai" and d2["source"] == "genai":
            assert d1["reply"] != d2["reply"], "Question and statement should get different response styles"

    @pytest.mark.asyncio
    async def test_different_roles_produce_different_responses(self, transport):
        """
        The same question from a fan and from staff should yield role-appropriate replies.

        Fan replies use public-friendly language; staff replies use operational language.
        """
        question = "What's the crowd status?"
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r_fan   = await client.post("/api/v1/chat", json={"message": question, "language": "en", "user_role": "fan"})
            r_staff = await client.post("/api/v1/chat", json={"message": question, "language": "en", "user_role": "staff"})

        assert r_fan.status_code == 200
        assert r_staff.status_code == 200
        d_fan, d_staff = r_fan.json(), r_staff.json()
        assert "reply" in d_fan and "reply" in d_staff
        if d_fan["source"] == "genai" and d_staff["source"] == "genai":
            assert d_fan["reply"] != d_staff["reply"], "Different roles should get role-appropriate responses"

    @pytest.mark.asyncio
    async def test_response_consistency_for_repeated_query(self, transport):
        """
        Asking the same question twice should produce stable, non-garbage responses.

        Both replies must be of reasonable length and use the same source tag.
        """
        message = "What's the weather like?"
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r1 = await client.post("/api/v1/chat", json={"message": message, "language": "en", "user_role": "fan"})
            r2 = await client.post("/api/v1/chat", json={"message": message, "language": "en", "user_role": "fan"})

        assert r1.status_code == 200
        assert r2.status_code == 200
        d1, d2 = r1.json(), r2.json()
        assert d1["source"] == d2["source"]
        assert 10 < len(d1["reply"]) < 1000
        assert 10 < len(d2["reply"]) < 1000


# ---------------------------------------------------------------------------
# Multilingual behaviour tests
# ---------------------------------------------------------------------------

class TestMultilingualBehaviour:
    """Verify that language codes are honoured in chat responses."""

    @pytest.mark.asyncio
    async def test_english_and_spanish_replies_differ(self, transport):
        """
        The same question in English and Spanish should produce language-matched replies.

        When GenAI is active the Spanish response is expected to contain common
        Spanish function words (``el``, ``la``, ``en``, etc.).
        """
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r_en = await client.post("/api/v1/chat", json={"message": "Where is the restroom?",  "language": "en", "user_role": "fan"})
            r_es = await client.post("/api/v1/chat", json={"message": "¿Dónde está el baño?",    "language": "es", "user_role": "fan"})

        assert r_en.status_code == 200
        assert r_es.status_code == 200
        d_en, d_es = r_en.json(), r_es.json()
        assert d_en["language"] == "en"
        assert d_es["language"] == "es"
        if d_en["source"] == "genai" and d_es["source"] == "genai":
            assert d_en["reply"] != d_es["reply"], "Responses must be in different languages"
            spanish_indicators = {"el", "la", "está", "los", "las", "en"}
            has_spanish = any(w in d_es["reply"].lower() for w in spanish_indicators)
            assert has_spanish or d_es["source"] == "fallback", \
                "Spanish GenAI response should contain Spanish words"


# ---------------------------------------------------------------------------
# Fallback mode tests
# ---------------------------------------------------------------------------

class TestFallbackMode:
    """Verify that fallback mode returns helpful, non-error replies."""

    @pytest.mark.asyncio
    async def test_common_questions_return_substantive_replies(self, transport):
        """
        A range of common fan questions should each produce a substantive reply
        (length > 20 chars) that contains no error or exception language.
        """
        test_cases = [
            "hi",
            "where is gate 5?",
            "what's the crowd like?",
            "how do I get there by bus?",
        ]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            for message in test_cases:
                response = await client.post(
                    "/api/v1/chat",
                    json={"message": message, "language": "en", "user_role": "fan"},
                )
                assert response.status_code == 200, f"Failed for message: {message!r}"
                data = response.json()
                assert "reply" in data
                reply_lower = data["reply"].lower()
                assert len(data["reply"]) > 20, f"Reply too short for: {message!r}"
                assert "error" not in reply_lower, f"Reply contains 'error' for: {message!r}"
                assert "exception" not in reply_lower, f"Reply contains 'exception' for: {message!r}"
