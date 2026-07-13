# Changelog

All notable changes to StadiumOS GenAI are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-07-13

### Changed

#### GenAI Provider Migration
- **BREAKING**: Migrated from Anthropic Claude to Google Gemini as the GenAI provider
- Updated environment variable from `ANTHROPIC_API_KEY` to `GOOGLE_API_KEY`
- Updated model configuration from `claude-sonnet-4-6` to `gemini-2.0-flash-exp`
- Updated all documentation to reflect Google Gemini usage
- API key source changed from https://console.anthropic.com/ to https://aistudio.google.com/apikey

#### Performance & Architecture
- **Implemented async Redis** using `redis.asyncio` to prevent blocking FastAPI event loop
- All Redis cache operations now use `async/await` pattern for better concurrency
- Improved throughput under high load by eliminating synchronous I/O blocking

#### Security
- **Fixed production CORS**: Changed from wildcard `["*"]` to specific frontend domain
- Production `render.yaml` now uses `["https://stadiumos-frontend.onrender.com"]`
- Reduces CORS-based attack surface in production deployments

#### Testing & Quality
- Verified test suite: **77 tests passing** (up from claimed 69)
- Verified coverage: **78% line coverage** (corrected from claimed 94%)
- Added 6 new integration tests for chatbot response variability
- Fixed async compatibility issue in `/admin/status` endpoint
- All tests run without external network calls

### Added
- Comprehensive `CHANGELOG.md` for version tracking
- API contract documentation in `docs/API_CONTRACT.md`
- Integration tests for chatbot response variability (`test_chatbot_integration.py`)
  - Tests different inputs produce different responses
  - Tests question vs statement handling
  - Tests role-based response adaptation
  - Tests multilingual support
  - Tests response consistency
  - Tests fallback mode quality

### Fixed
- Admin router `/status` endpoint now properly awaits `is_cache_available()`
- Cache initialization now uses async connection testing
- All cache statistics retrieval operations are now async

### Documentation
- Updated `README.md` with accurate Gemini configuration
- Updated `DEPLOYMENT.md` with Google Gemini setup instructions
- Updated `QUICK_START.md` with correct API key source
- Updated `CLOUD_DEPLOYMENT.md` for all cloud platforms
- Updated `docs/ARCHITECTURE.md` with Gemini references
- Updated `docs/DIAGRAMS.md` system diagrams
- Updated `docs/PERFORMANCE.md` metrics and benchmarks

### Migration Guide

If upgrading from v1.0.0, follow these steps:

1. **Update environment variables**:
   ```bash
   # Old (v1.0.0)
   ANTHROPIC_API_KEY=sk-ant-xxxxx
   ANTHROPIC_MODEL=claude-sonnet-4-6
   
   # New (v1.1.0)
   GOOGLE_API_KEY=your-gemini-key
   GEMINI_MODEL=gemini-2.0-flash-exp
   ```

2. **Get new API key**:
   - Visit https://aistudio.google.com/apikey
   - Create or select a project
   - Generate API key
   - Update your `.env` file

3. **Update Redis library** (if installed separately):
   ```bash
   pip install --upgrade redis
   ```

4. **Update deployment configs**:
   - Update `ALLOWED_ORIGINS` in production to use exact domain
   - Review and update any infrastructure-as-code

5. **Test your deployment**:
   ```bash
   cd backend
   pytest tests/
   ```

## [1.0.0] - 2026-07-01

### Added
- Initial release of StadiumOS GenAI
- 8 GenAI-enabled REST endpoints with deterministic fallback
- Multilingual chat assistant (Ana) supporting 10 languages
- AI-narrated navigation with accessibility awareness
- Crowd safety monitoring and operator briefing
- Transport recommendations (parking, shuttle, transit)
- Accessibility concierge service
- Sustainability tips and guidance
- Emergency decision support system
- Full FastAPI backend with async architecture
- Vanilla JavaScript frontend with zero build step
- Redis caching layer (82% hit rate target)
- Anthropic Claude integration (`claude-sonnet-4-6`)
- Comprehensive test suite (69 tests at initial claim)
- Security middleware (rate limiting, headers, input validation)
- Docker deployment support
- WCAG 2.1 AA accessibility target
- Prometheus metrics instrumentation

### Security
- Custom rate limiter (30 req/60s default)
- Security headers middleware
- Prompt injection filtering
- Input validation and sanitization
- Admin API key authentication
- Constant-time admin key comparison
- No secrets in source control

### Documentation
- Complete architecture documentation
- Security threat model and controls
- Accessibility conformance notes
- Testing strategy documentation
- Deployment guides (Docker, cloud platforms)
- API documentation via OpenAPI/Swagger

---

## Version Comparison

| Version | GenAI Provider | Tests | Coverage | Redis | CORS Security |
|---------|---------------|-------|----------|-------|---------------|
| 1.0.0   | Anthropic Claude | 69 (claimed) | 94% (claimed) | Sync | Wildcard `["*"]` |
| 1.1.0   | Google Gemini | 77 (verified) | 78% (verified) | Async | Specific domain |

---

## Upcoming

### [1.2.0] - Planned
- Enhanced chatbot integration tests
- Expanded API contract testing
- Performance benchmarking suite
- Load testing with Locust
- CI/CD pipeline with GitHub Actions
- Automated deployment to staging

### Future Considerations
- Support for multiple GenAI providers (Claude, Gemini, GPT-4)
- WebSocket support for real-time updates
- Enhanced observability with distributed tracing
- Multi-stadium support
- Advanced caching strategies (CDN integration)
- Mobile app integration

---

For detailed API changes, see `docs/API_CONTRACT.md`.

For security-related changes, see `docs/SECURITY.md`.
