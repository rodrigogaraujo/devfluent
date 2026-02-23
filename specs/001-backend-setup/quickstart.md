# Quickstart: Backend Project Setup

**Feature**: 001-backend-setup
**Date**: 2026-02-22

## Prerequisites

- Python 3.12+
- Docker & Docker Compose (for local PostgreSQL + Redis)
- Telegram bot token (from @BotFather)
- OpenAI API key
- Groq API key

## Setup

### 1. Clone and enter backend directory

```bash
cd devfluent/backend
```

### 2. Create virtual environment and install dependencies

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

### 3. Start local infrastructure

```bash
docker compose -f ../docker-compose.yml up -d
```

This starts PostgreSQL 16 (port 15432) and Redis 7 (port 16379).

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env with your credentials:
#   TELEGRAM_BOT_TOKEN=<from @BotFather>
#   OPENAI_API_KEY=<your key>
#   GROQ_API_KEY=<your key>
#   DATABASE_URL=postgresql+asyncpg://devfluent:devfluent@localhost:15432/devfluent
#   REDIS_URL=redis://localhost:16379
```

### 5. Run database migrations

```bash
alembic upgrade head
```

### 6. Start the server

```bash
uvicorn backend.src.main:app --reload --port 18001
```

### 7. Verify health

```bash
curl http://localhost:18001/health
# Expected: {"status": "ok", "version": "0.1.0"}
```

### 8. Set up Telegram webhook (for local testing with ngrok)

```bash
# In a separate terminal:
ngrok http 18001

# Set webhook URL in .env:
# TELEGRAM_WEBHOOK_URL=https://<ngrok-id>.ngrok.io

# Restart server — webhook is set automatically on startup
```

### 9. Test the bot

Open Telegram, find your bot, send `/start`. You should receive a welcome message.

## Running Tests

```bash
# All tests (no external API keys required)
pytest tests/ -v

# Specific test file
pytest tests/test_conversation.py -v

# With coverage
pytest tests/ --cov=src --cov-report=term-missing
```

## Project Structure

```
backend/
├── src/
│   ├── main.py          # FastAPI app + webhook
│   ├── config.py         # All settings (pydantic-settings)
│   ├── database.py       # Async SQLAlchemy setup
│   ├── bot/              # Telegram handlers + middleware
│   ├── core/             # Business logic (conversation, assessment, etc.)
│   ├── ai/               # Provider abstractions (LLM, STT, TTS, Context)
│   ├── channels/         # MessageChannel abstraction
│   ├── models/           # SQLAlchemy models + repositories
│   ├── services/         # Billing, notifications, reports
│   └── utils/            # Audio, storage, token counting
├── tests/                # pytest tests (all mocked, no API deps)
├── migrations/           # Alembic migrations
└── scripts/              # Seed data, manual test scripts
```

## Key Commands

| Command | Description |
|---------|-------------|
| `uvicorn backend.src.main:app --reload` | Start dev server |
| `alembic revision --autogenerate -m "description"` | Create migration |
| `alembic upgrade head` | Apply migrations |
| `alembic downgrade -1` | Rollback last migration |
| `pytest tests/ -v` | Run tests |
| `ruff check src/` | Lint code |
| `ruff format src/` | Format code |

## Environment Variables

All variables are declared in `backend/.env.example` and loaded via `backend/src/config.py` (pydantic-settings). Never use `os.getenv()` directly in application code.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| TELEGRAM_BOT_TOKEN | Yes | — | From @BotFather |
| TELEGRAM_WEBHOOK_URL | Yes | — | Public URL for webhook |
| OPENAI_API_KEY | Yes | — | For GPT-4o + TTS |
| GROQ_API_KEY | Yes | — | For Whisper STT |
| DATABASE_URL | Yes | — | PostgreSQL connection string |
| REDIS_URL | No | "" | Upstash Redis URL |
| R2_ACCOUNT_ID | No | "" | Cloudflare R2 (optional) |
| R2_ACCESS_KEY | No | "" | R2 access key |
| R2_SECRET_KEY | No | "" | R2 secret key |
| R2_BUCKET | No | "devfluent-audio" | R2 bucket name |
| R2_PUBLIC_URL | No | "" | R2 public URL |
| SENTRY_DSN | No | "" | Sentry error tracking |
| ADMIN_TELEGRAM_ID | No | "" | Admin user for /activate etc. |
| MAX_CONTEXT_TOKENS | No | 4000 | Token budget for context |
| CONVERSATION_TIMEOUT_MIN | No | 30 | Minutes before auto-end |
| MAX_MESSAGES_PER_DAY | No | 100 | Rate limit per user |
| TTS_SPEED | No | 1.0 | Default TTS speed |

## Deployment (Railway)

```bash
# Push to main triggers CI → deploy
git push origin main

# Manual deploy
railway up
```

Railway auto-detects the Dockerfile, runs migrations on startup, and exposes the webhook endpoint at the configured domain.
