# Research: Backend Project Setup

**Feature**: 001-backend-setup
**Date**: 2026-02-22
**Status**: Complete — all unknowns resolved

## Research Tasks

### R1: FastAPI + python-telegram-bot (PTB) v21+ Integration

**Decision**: Use PTB v21+ in webhook mode integrated with FastAPI via a shared lifespan handler.

**Rationale**: PTB v21+ is fully async-native and supports webhook mode via `Application.builder()`. FastAPI handles the HTTP endpoint (`POST /webhook/telegram`), receives the raw JSON, deserializes it with `Update.de_json()`, and delegates to PTB's `process_update()`. This avoids polling (incompatible with Railway's ephemeral containers) and keeps a single HTTP server.

**Key patterns**:
- Register PTB handlers during FastAPI lifespan startup
- Set webhook URL via `application.bot.set_webhook()` in lifespan
- Webhook endpoint deserializes update and delegates: `await application.process_update(update)`
- PTB v21+ uses `ApplicationBuilder` pattern, not the deprecated `Updater`

**Alternatives considered**:
- aiogram (lighter, but smaller ecosystem and less documentation)
- Raw Telegram API via httpx (more boilerplate, loses PTB's handler/middleware system)
- PTB polling mode (incompatible with Railway, requires persistent process)

### R2: Async SQLAlchemy 2.0+ with Alembic

**Decision**: Use SQLAlchemy 2.0+ with `asyncpg` driver and `async_sessionmaker`.

**Rationale**: SQLAlchemy 2.0+ natively supports async via `create_async_engine`. Using `mapped_column()` (not legacy `Column()`) with type-annotated `Mapped[]` fields. Alembic autogenerate works with async engines via the `run_async()` wrapper in `env.py`.

**Key patterns**:
- `create_async_engine(database_url)` in `backend/src/database.py`
- `async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)`
- `get_db()` async generator for FastAPI dependency injection
- `DeclarativeBase` with `BaseMixin` for shared `id` (UUID) and `created_at` columns
- Alembic `env.py` uses `connectable = async_engine.connect()` with `run_async()`

**Alternatives considered**:
- Tortoise ORM (simpler async, but weaker migration tooling)
- Raw asyncpg (no ORM, too much boilerplate for 8 tables)
- Prisma Python (immature async support)

### R3: OpenAI SDK for LLM + TTS

**Decision**: Use `openai.AsyncOpenAI` for both GPT-4o chat completions and gpt-4o-mini-tts speech synthesis.

**Rationale**: Single SDK (`openai>=1.30`) handles both LLM and TTS. Chat completions return token usage in response. TTS returns streaming response — use `.read()` for bytes. Output format `opus` is directly compatible with Telegram voice messages (`send_voice()`).

**Key patterns**:
- LLM: `client.chat.completions.create(model="gpt-4o", messages=[...])` → `LLMResponse` with `usage.prompt_tokens`, `usage.completion_tokens`
- LLM JSON: `response_format={"type": "json_object"}` for structured extraction
- TTS: `client.audio.speech.create(model="gpt-4o-mini-tts", voice="nova", input=text, response_format="opus")` → streaming → `.read()` for bytes
- TTS speed varies by level: 0.85 (L1), 1.0 (L2), 1.05 (L3), 1.10 (L4)

**Alternatives considered**:
- Claude API (better reasoning but GPT-4o better at roleplay/teaching per ADR-003)
- Edge TTS (free but lower quality per ADR-002 — kept as future fallback)
- ElevenLabs (higher quality but ~5x cost)

### R4: Groq SDK for STT (Whisper)

**Decision**: Use `groq.AsyncGroq` with `whisper-large-v3` model.

**Rationale**: Groq offers free-tier Whisper transcription with <1s latency. Accepts `.oga` (Opus) audio directly from Telegram without format conversion. Returns `STTResult` with text, language, and duration.

**Key patterns**:
- `client.audio.transcriptions.create(file=("audio.ogg", audio_bytes), model="whisper-large-v3", language="en")`
- Returns `Transcription` object with `.text`
- File parameter accepts bytes with filename hint for format detection

**Alternatives considered**:
- OpenAI Whisper API (paid, same quality, no speed advantage)
- Self-hosted Whisper (complexity too high for MVP — Phase 3 per roadmap)

### R5: Context Assembly Strategy (3-Layer)

**Decision**: SQLContextProvider with 3 layers, token budget of ~4K tokens.

**Rationale**: For 10 users with <3 months of data, SQL queries are sufficient and simpler than vector search. The `ContextProvider` interface allows seamless upgrade to `VectorContextProvider` (Phase 2) when users accumulate 50+ conversation summaries.

**Key patterns**:
- Layer 1 (User Profile, ~200 tokens): user record + top 5 error patterns
- Layer 2 (Conversation History, ~2-3K tokens): last 15 messages from current session, reversed to chronological
- Layer 3 (Memory Summaries, ~500-1K tokens): last 5 conversation summaries by recency
- Token counting via `tiktoken.encoding_for_model("gpt-4o")`
- Truncation strategy: if history exceeds budget, remove oldest messages (keep minimum 5)

**Alternatives considered**:
- pgvector from day 1 (over-engineering per ADR-004)
- RAG pipeline (requires exercise/interview bank that doesn't exist yet)
- No memory (defeats product value proposition)

### R6: Audio Pipeline (Telegram ↔ STT ↔ TTS)

**Decision**: Direct byte streaming without intermediate file storage for MVP.

**Rationale**: Telegram sends `.oga` (Opus) files. Groq Whisper accepts them directly. OpenAI TTS outputs `opus` format — directly sendable as `send_voice()`. No format conversion needed in the happy path. R2 storage is opt-in (upload if credentials configured, skip otherwise).

**Key patterns**:
- Download: `bot.get_file(file_id)` → `file.download_as_bytearray()`
- Transcribe: pass bytes directly to Groq (no temp files)
- Synthesize: OpenAI TTS returns opus bytes
- Send: `bot.send_voice(chat_id, audio_bytes)` (not `send_audio` — different Telegram rendering)
- Optional: upload to R2 with key `audio/{user_id}/{conversation_id}/{message_id}.opus`

**Alternatives considered**:
- Always store in R2 first (unnecessary for MVP, adds latency)
- Convert to MP3 (unnecessary — Opus works end-to-end)
- Use pydub for all conversion (only needed if edge cases arise with format)

### R7: Deployment (Railway + Docker)

**Decision**: Single Dockerfile deploying to Railway with health check and auto-migrations.

**Rationale**: Railway provides managed container hosting with automatic HTTPS, custom domains, and env var management. Single container per ADR-005 (monolith). Alembic migrations run in Dockerfile CMD before uvicorn starts.

**Key patterns**:
- Base: `python:3.12-slim` + ffmpeg (for pydub edge cases)
- CMD: `sh -c "alembic upgrade head && uvicorn backend.src.main:app --host 0.0.0.0 --port ${PORT:-8000}"`
- Health check: `GET /health` returning 200
- Railway config: `railway.toml` with Dockerfile builder
- CI: GitHub Actions — ruff lint + pytest on push, deploy on main

**Alternatives considered**:
- Fly.io (similar but Railway has simpler Python DX)
- AWS Lambda (cold start incompatible with webhook mode)
- Self-hosted VPS (more ops burden for solo developer)

### R8: Rate Limiting and Caching (Redis/Upstash)

**Decision**: Redis (Upstash) for rate limiting counters and assessment state. Cache-aside for frequently accessed data.

**Rationale**: Upstash offers free tier with REST API. Used for: (1) rate limiting via `msg_count:{user_id}:{date}` keys with TTL, (2) assessment state machine state with 1h TTL, (3) optional cache-aside for user level and active study plan.

**Key patterns**:
- Rate limit: `INCR msg_count:{user_id}:{date}` with `EXPIRE 86400`
- Assessment state: `SET assessment:{user_id} {json}` with `EX 3600`
- Cache-aside: check Redis first → query DB on miss → cache result with 5min TTL

**Alternatives considered**:
- In-memory rate limiting (lost on restart, multi-instance unsafe)
- Database-backed rate limiting (unnecessary queries)
- No rate limiting (risks API cost blowout)

### R9: Structured Logging and Monitoring

**Decision**: Sentry for error tracking + structlog for JSON logging + PostHog for product analytics.

**Rationale**: Sentry catches unhandled exceptions and can track performance (traces_sample_rate=0.1). structlog provides structured JSON logging with context (user_id, conversation_id, request_id). PostHog tracks product events (onboarding complete, level up, mock interview, etc.).

**Key patterns**:
- Sentry init in `main.py` lifespan with FastAPI integration
- structlog processors: add timestamp, user_id, conversation_id, format to JSON
- PostHog events: `posthog.capture(user_id, "onboarding_completed", {level: 2})`
- No bare `print()` or unstructured `logging.info()` per constitution V.

**Alternatives considered**:
- Just print + CloudWatch (unstructured, hard to query)
- Datadog (overkill for 10 users, expensive)
- Self-hosted Grafana/Loki (too much ops)

### R10: Multi-Select InlineKeyboard for Onboarding (Tech Profile + Goals)

**Decision**: Implement multi-select via InlineKeyboard with toggle emojis and a dedicated confirm button.

**Rationale**: PTB v21+ supports `InlineKeyboardMarkup` with callback queries. For multi-select, each option is a button with callback_data encoding the selection state. When tapped, the handler toggles the selection (adds/removes checkmark emoji prefix) and edits the message to show updated keyboard. A "Confirm" button submits the selections.

**Key patterns**:
- Single-select: each button sends `callback_data="tech_role:{value}"` — handler saves immediately and advances to next step
- Multi-select: buttons send `callback_data="toggle:tech_stack:{value}"` — handler toggles in Redis state, re-renders keyboard with `✓` prefix on selected items
- Confirm button: `callback_data="confirm:tech_stack"` — handler reads final selections from Redis state and saves to user record
- All onboarding state is persisted in Redis with 1h TTL per `assessment:{user_id}` key
- Conditional flow: `TARGET_STACK` step only appears if `goals` includes `"technical_interview"`

**Keyboard rendering example**:
```
[Python] [✓ JavaScript/TS] [Java]
[✓ Go] [React] [Node.js]
[AWS] [✓ Kubernetes] [SQL]
[Docker] [Other]
[✅ Confirm]
```

**Alternatives considered**:
- Free-text input (error-prone, hard to normalize)
- Single message with numbered options (less interactive, poor UX)
- Web-based form (breaks Telegram-native experience)

## Summary

All 10 research areas resolved. No NEEDS CLARIFICATION items remain. The technology stack is fully ratified per PROJECT_SPEC_V3 §6 and constitution v2.0.0. Key decisions: keep everything simple for MVP — SQL context (not vector), direct byte streaming (not R2-first), single container (not microservices), manual PIX (not Stripe). Multi-select InlineKeyboard pattern enables the 5-phase onboarding flow for tech profile + goal collection.
