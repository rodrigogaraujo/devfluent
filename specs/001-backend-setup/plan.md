# Implementation Plan: Backend Project Setup

**Branch**: `001-backend-setup` | **Date**: 2026-02-22 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-backend-setup/spec.md`
**Base reference**: [PLAN.md](../../PLAN.md) (adapted to constitution v2.0.0)

## Summary

Set up the complete DevFluent backend: FastAPI server with Telegram bot integration, PostgreSQL database with 8-table schema, AI provider abstractions (LLM, STT, TTS, Context), conversation engine with 3-layer memory architecture (profile including tech role/stack/goals ~300 tokens, history ~2-3K tokens, summaries ~500-1K tokens), 5-phase onboarding assessment (self-declaration → tech profile → goal setting → written → speaking), goal-oriented study plans, personalized mock interviews, summary generation, and deployment pipeline. All code lives in `backend/` as a self-contained Python package following the layered architecture defined in the constitution.

## Technical Context

**Language/Version**: Python 3.12+ (async-first, type hints mandatory)
**Primary Dependencies**: FastAPI, python-telegram-bot (PTB) v21+ (async), OpenAI SDK, Groq SDK, SQLAlchemy 2.0+ (async), Alembic, pydantic-settings, httpx, tiktoken, APScheduler, boto3, sentry-sdk
**Storage**: PostgreSQL (Supabase) via SQLAlchemy ORM + Alembic migrations; Redis (Upstash) for caching/rate limiting; Cloudflare R2 for audio files
**Testing**: pytest with async support, mocked providers (no external API deps in tests)
**Target Platform**: Linux server (Railway) — single-container deployment with webhook mode
**Project Type**: Web service (monolito modular FastAPI — ADR-005)
**Performance Goals**: Response within 5s for text, 10s for voice messages (10 users MVP)
**Constraints**: ~4-8K token budget per LLM interaction, 100 messages/user/day rate limit, ~R$209/month total infrastructure cost
**Scale/Scope**: 10 internal testers, 8 database tables, 6 provider abstractions, 14 implementation tasks

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Notes |
|---|-----------|--------|-------|
| I | Simplicity First | PASS | MVP for 10 testers. No speculative features. SQL context (not vector). Manual PIX (not Stripe). |
| II | Layered Architecture | PASS | Handlers (bot/) → Services (core/) → Repositories (models/) → Database. AI Orchestration (ai/) called only by services. |
| III | Provider Abstraction | PASS | 6 interfaces: LLMProvider, STTProvider, TTSProvider, ContextProvider, MessageChannel, StorageProvider. Each with ABC + concrete impl. |
| IV | Validate at Boundaries | PASS | Telegram webhooks validated via Pydantic. Config via pydantic-settings. API responses validated against expected schemas. |
| V | Structured Error Handling | PASS | Centralized error handler at handler level. Structured JSON logging. Sentry for unhandled exceptions. PostHog for analytics. |
| VI | Repository Pattern | PASS | Each entity has repository module in `backend/src/models/`. Explicit transactions. Eager loading for N+1 prevention. |
| VII | Test-Driven Quality | PASS | Unit tests for services. Prompt validation tests. Integration tests for flows. Context assembly tests with token budget verification. |
| VIII | Library-First | PASS | Using established libraries: tiktoken (token counting), pydub (audio), APScheduler (cron), boto3 (S3/R2). No custom reinventions. |

**Gate result**: ALL PASS — proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/001-backend-setup/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── webhook-api.md
│   └── provider-interfaces.md
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── pyproject.toml
├── Dockerfile
├── .env.example
├── alembic.ini
├── migrations/
│   ├── env.py
│   └── versions/
├── src/
│   ├── __init__.py
│   ├── main.py              # FastAPI app factory + webhook endpoint
│   ├── config.py            # Pydantic Settings (all env vars)
│   ├── database.py          # Async SQLAlchemy engine + session
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── handlers.py      # Command + message handlers
│   │   ├── keyboards.py     # InlineKeyboard builders
│   │   └── middleware.py    # Rate limit, active check, user lookup
│   ├── core/
│   │   ├── __init__.py
│   │   ├── conversation.py  # ConversationEngine (core loop)
│   │   ├── assessment.py    # AssessmentEngine (onboarding)
│   │   ├── study_plan.py    # StudyPlanGenerator
│   │   ├── mock_interview.py# MockInterviewEngine
│   │   ├── feedback.py      # FeedbackAnalyzer (error/vocab extraction)
│   │   ├── summary.py       # SummaryGenerator
│   │   └── vocabulary.py    # VocabularyTracker (SM-2 light)
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── llm.py           # LLMProvider ABC + OpenAILLM
│   │   ├── stt.py           # STTProvider ABC + GroqSTT
│   │   ├── tts.py           # TTSProvider ABC + OpenAITTS
│   │   ├── context.py       # ContextProvider ABC + SQLContextProvider
│   │   └── prompts/
│   │       ├── __init__.py
│   │       ├── base.py      # System prompt template
│   │       ├── levels.py    # Level-specific prompts (1-4)
│   │       ├── assessment.py# Onboarding + level check prompts
│   │       └── interview.py # Mock interview prompt
│   ├── channels/
│   │   ├── __init__.py
│   │   ├── base.py          # MessageChannel ABC
│   │   └── telegram.py      # TelegramChannel
│   ├── models/
│   │   ├── __init__.py      # Imports all models for Alembic
│   │   ├── base.py          # DeclarativeBase + BaseMixin (id, timestamps)
│   │   ├── user.py          # User, UserErrorPatterns
│   │   ├── conversation.py  # Conversation, Message
│   │   ├── study_plan.py    # StudyPlan
│   │   ├── assessment.py    # Assessment
│   │   ├── vocabulary.py    # UserVocabulary
│   │   └── metrics.py       # WeeklyMetrics
│   ├── services/
│   │   ├── __init__.py
│   │   ├── billing.py       # Admin commands (activate/deactivate)
│   │   ├── notifications.py # Daily/weekly notifications via APScheduler
│   │   └── reports.py       # Weekly report generation
│   └── utils/
│       ├── __init__.py
│       ├── audio.py         # Download, convert, upload audio
│       ├── storage.py       # StorageProvider ABC + R2Storage
│       └── tokens.py        # Token counting/budgeting via tiktoken
├── tests/
│   ├── conftest.py          # Fixtures: db session, mock providers
│   ├── test_conversation.py
│   ├── test_assessment.py
│   ├── test_context.py
│   ├── test_prompts.py
│   └── test_interview.py
└── scripts/
    ├── seed_vocab.py        # Base vocabulary by level
    └── create_test_user.py  # Realistic test user
```

**Structure Decision**: Backend-only per constitution's Repository Structure & Growth Strategy. The `backend/` directory is self-contained with its own `pyproject.toml`, tests, and migrations. Future `web/` (Next.js) and `mobile/` (React Native) will be added as sibling directories only after product validation (PROJECT_SPEC_V3 §11 decision gate). All paths from PLAN.md reconciled from `src/` to `backend/src/`.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| 6 provider abstractions | Constitution III mandates provider abstraction for LLM, STT, TTS, Context, Channel. StorageProvider added for R2 opt-in. | Direct API calls would couple core domain to specific vendors, violating swappability requirement per ADR-001 through ADR-004. |
| 8 database tables | Data model from PROJECT_SPEC_V3 §5 serves 8 distinct entities with different lifecycles. | Fewer tables would require JSONB catch-alls or denormalization that complicates querying for context assembly (3 layers). |

## Task Dependency Graph

```
TASK 0  — Scaffolding           ← No dependency
TASK 1  — Database Models       ← depends on TASK 0
TASK 2  — AI Providers          ← depends on TASK 0
TASK 3  — Context Assembly      ← depends on TASK 1, TASK 2
TASK 4  — Telegram Bot          ← depends on TASK 0, TASK 2
TASK 5  — Conversation Engine   ← depends on TASK 3, TASK 4 (★ core)
TASK 6  — Assessment            ← depends on TASK 5
TASK 7  — Study Plan            ← depends on TASK 1, TASK 5
TASK 8  — Mock Interview        ← depends on TASK 5
TASK 9  — Summaries + Reports   ← depends on TASK 5
TASK 10 — Billing (admin)       ← depends on TASK 4
TASK 11 — Storage (R2)          ← depends on TASK 4 (optional)
TASK 12 — DevOps                ← depends on TASK 5 (can parallel)
TASK 13 — Testing               ← depends on all

Critical path: 0 → 1 → 2 → 3 → 5 → 6 → 8 → 9 → 12
```
