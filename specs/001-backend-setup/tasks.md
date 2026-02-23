# Tasks: Backend Project Setup

**Input**: Design documents from `/specs/001-backend-setup/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/webhook-api.md, contracts/provider-interfaces.md, research.md, quickstart.md
**Branch**: `001-backend-setup`
**Date**: 2026-02-22

**Organization**: Tasks grouped by user story (P1 → P2 → P3 → P4) for independent implementation and testing.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependency on incomplete tasks in same batch)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- All paths relative to repository root

---

## Phase 1: Setup (Project Initialization)

**Purpose**: Create backend directory structure and configure project dependencies

- [X] T001 Create backend/ directory tree with all subdirectories and `__init__.py` files per plan.md: `backend/src/`, `backend/src/bot/`, `backend/src/core/`, `backend/src/ai/`, `backend/src/ai/prompts/`, `backend/src/channels/`, `backend/src/models/`, `backend/src/services/`, `backend/src/utils/`, `backend/tests/`, `backend/migrations/versions/`, `backend/scripts/`
- [X] T002 [P] Create backend/pyproject.toml — Python 3.12+, project name "devfluent-backend", dependencies: fastapi, uvicorn[standard], python-telegram-bot[webhooks]>=21.0, openai>=1.30, groq, sqlalchemy[asyncio]>=2.0, asyncpg, alembic, pydantic-settings, httpx, tiktoken, structlog, sentry-sdk[fastapi], redis[hiredis], boto3, pydub, apscheduler; dev extras: pytest, pytest-asyncio, ruff, coverage, httpx (test client); entry point: `backend.src.main:app`
- [X] T003 [P] Create backend/.env.example with all environment variables per quickstart.md: TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_URL, OPENAI_API_KEY, GROQ_API_KEY, DATABASE_URL (postgresql+asyncpg://), REDIS_URL, R2_ACCOUNT_ID, R2_ACCESS_KEY, R2_SECRET_KEY, R2_BUCKET, R2_PUBLIC_URL, SENTRY_DSN, POSTHOG_API_KEY, ADMIN_TELEGRAM_ID, MAX_CONTEXT_TOKENS=4000, CONVERSATION_TIMEOUT_MIN=30, MAX_MESSAGES_PER_DAY=100, TTS_SPEED=1.0

---

## Phase 2: Foundational (Core Infrastructure)

**Purpose**: Database, configuration, provider abstractions, and HTTP server that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

### Core Configuration

- [X] T004 Implement backend/src/config.py — `Settings` class via pydantic-settings with `model_config = SettingsConfigDict(env_file=".env")`. Fields matching all .env.example variables with types: str for API keys/URLs, int for MAX_CONTEXT_TOKENS/CONVERSATION_TIMEOUT_MIN/MAX_MESSAGES_PER_DAY, float for TTS_SPEED. Optional fields (default "") for R2_*, SENTRY_DSN, POSTHOG_API_KEY, REDIS_URL. Export `settings = Settings()` singleton
- [X] T005 Implement backend/src/database.py — `create_async_engine(settings.DATABASE_URL)`, `async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)`, `async def get_db()` async generator yielding AsyncSession. Import Settings from config.py

### Independent Abstractions (all [P] — no cross-dependencies)

- [X] T006 [P] Implement backend/src/models/base.py — `class Base(DeclarativeBase): pass` + `class BaseMixin`: `id: Mapped[UUID]` as PK with `default=uuid4`, `created_at: Mapped[datetime]` with `server_default=func.now()`, `updated_at: Mapped[datetime]` with `server_default=func.now(), onupdate=func.now()`. Use `mapped_column()` and `Mapped[]` (SQLAlchemy 2.0+ style)
- [X] T007 [P] Implement backend/src/ai/llm.py — `LLMProvider(ABC)` with `async def chat(system_prompt, messages, temperature=0.7, max_tokens=1000) -> LLMResponse` and `async def chat_json(system_prompt, messages, schema=None) -> dict`. `@dataclass LLMResponse: content, input_tokens, output_tokens, model`. `OpenAILLM(LLMProvider)` using `openai.AsyncOpenAI` with `client.chat.completions.create()`. chat_json uses `response_format={"type": "json_object"}`
- [X] T008 [P] Implement backend/src/channels/base.py — `MessageChannel(ABC)` with `send_text(chat_id, text)`, `send_audio(chat_id, audio, caption="")`, `send_keyboard(chat_id, text, options)`, `download_audio(file_id) -> bytes`. `@dataclass IncomingMessage: chat_id, user_id, user_name, text, audio_file_id, is_audio, raw`
- [X] T009 [P] Implement backend/src/utils/tokens.py — `count_tokens(text: str, model: str = "gpt-4o") -> int` using `tiktoken.encoding_for_model()`. `truncate_messages(messages: list[dict], max_tokens: int, keep_minimum: int = 5) -> list[dict]` removing oldest messages first

### Database Models (all [P] — depend on T006 base.py)

- [X] T010 [P] Implement backend/src/models/user.py — `User(BaseMixin, Base)` with all columns from data-model.md: telegram_id (BigInteger, unique, non-null), name (String(255)), email (String(255)), current_level (SmallInteger, default=1), cefr_estimate (String(2)), onboarding_done (Boolean, default=False), subscription (String(20), default="free"), weekly_goal_min (Integer, default=60), timezone (String(50), default="America/Sao_Paulo"), is_active (Boolean, default=False), tech_role (String(30), nullable), tech_stack (JSONB, default=[]), goals (JSONB, default=[]), target_stack (JSONB, default=[]), target_company (String(30), default="startup"). Also `UserErrorPattern(BaseMixin, Base)` with user_id FK, error_type (String(50)), error_detail (String(255)), correction (Text), occurrence_count (Integer, default=1), last_seen (DateTime). UniqueConstraint on (user_id, error_type, error_detail). Index on (user_id, occurrence_count DESC)
- [X] T011 [P] Implement backend/src/models/conversation.py — `Conversation(BaseMixin, Base)` with user_id FK, mode (String(30), non-null), topic (String(255)), level_at_time (SmallInteger), started_at (DateTime, server_default=now), ended_at (DateTime, nullable), summary (Text), errors_found (JSONB), new_vocab (JSONB). Indexes: (user_id, created_at DESC), partial on (user_id) WHERE summary IS NOT NULL. `Message(BaseMixin, Base)` with conversation_id FK, role (String(10), non-null), content_text (Text), content_audio (String(500)), transcription (Text), corrections (JSONB), pronunciation (JSONB), tokens_used (Integer). Indexes: (conversation_id, created_at), (conversation_id, created_at DESC)
- [X] T012 [P] Implement remaining model files — (a) backend/src/models/assessment.py: `Assessment(BaseMixin, Base)` with user_id FK, type (String(20), non-null), level_before (SmallInteger), level_after (SmallInteger), scores (JSONB), feedback (Text), conversation_id FK. (b) backend/src/models/study_plan.py: `StudyPlan(BaseMixin, Base)` with user_id FK, level (SmallInteger, non-null), week_number (SmallInteger, non-null), theme (String(255)), focus_skills (JSONB), target_vocab (JSONB), completed (Boolean, default=False). (c) backend/src/models/vocabulary.py: `UserVocabulary(BaseMixin, Base)` with user_id FK, word (String(255), non-null), context (Text), level_learned (SmallInteger), times_seen (Integer, default=1), times_used (Integer, default=0), next_review (DateTime), ease_factor (Float, default=2.5). UniqueConstraint (user_id, word), Index (user_id, next_review). (d) backend/src/models/metrics.py: `WeeklyMetrics(BaseMixin, Base)` with user_id FK, week_start (Date, non-null), minutes_practiced/messages_sent/audio_messages/new_words/errors_grammar/errors_pronunciation/streak_days/xp_earned (all Integer, default=0). UniqueConstraint (user_id, week_start)

### Integration (sequential — each depends on previous)

- [X] T013 Implement backend/src/models/__init__.py importing all model classes (User, UserErrorPattern, Conversation, Message, Assessment, StudyPlan, UserVocabulary, WeeklyMetrics) for Alembic discovery. Then set up Alembic: backend/alembic.ini (script_location=migrations, sqlalchemy.url from env), backend/migrations/env.py (async with run_async wrapper, import Base from models.base, target_metadata=Base.metadata). Generate initial migration with all 8 tables via `alembic revision --autogenerate -m "initial schema"`
- [X] T014 Implement backend/src/channels/telegram.py — `TelegramChannel(MessageChannel)` wrapping PTB Bot instance. `send_text`: `bot.send_message(chat_id, text, parse_mode="HTML")`. `send_audio`: `bot.send_voice(chat_id, audio)` (send_voice not send_audio — different Telegram rendering). `send_keyboard`: build `InlineKeyboardMarkup` from options list and `bot.send_message()` with reply_markup. `download_audio`: `bot.get_file(file_id)` then `file.download_as_bytearray()`
- [X] T015 Implement backend/src/bot/middleware.py — Three middleware functions for PTB v21+ handler pipeline: (1) `user_lookup`: find User by telegram_id or create with is_active=FALSE, attach to context.user_data. (2) `active_check`: if is_active=FALSE and command not in ["/start", "/help"], send waitlist message "You're on the waitlist! We'll activate you soon." and stop processing. (3) `rate_limit`: Redis INCR `msg_count:{user_id}:{date}` with EXPIRE 86400, if count > MAX_MESSAGES_PER_DAY send rate limit message "You've been practicing a lot today! Let's continue tomorrow." Graceful fallback if Redis unavailable (skip rate limit)
- [X] T016 Implement backend/src/main.py — FastAPI app with async lifespan: on startup init Sentry (if DSN configured), create DB engine, build PTB Application via `ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN).build()`, set webhook URL via `application.bot.set_webhook(settings.TELEGRAM_WEBHOOK_URL + "/webhook/telegram")`, create concrete providers (OpenAILLM, TelegramChannel), store in app.state. Routes: `GET /health` returning `{"status": "ok", "version": "0.1.0"}` (503 with `{"status": "degraded", "error": "database_unavailable"}` if DB check fails). `POST /webhook/telegram` receiving JSON, validating payload via `Update.de_json(data, application.bot)` (FR-010: PTB validates Telegram schema internally — reject malformed payloads with logged warning), delegating via `application.process_update(update)`, always returning 200. On shutdown: delete webhook, dispose engine. Configure structlog with JSON output, timestamp, user_id binding

**Checkpoint**: Foundation ready — FastAPI server starts, /health responds, webhook receives Telegram updates, database tables exist. User story implementation can now begin.

---

## Phase 3: User Story 1 — Developer Starts the Bot (Priority: P1) MVP

**Goal**: New user sends /start, completes 5-phase onboarding (self-declaration → tech profile → goals → written assessment → speaking assessment), gets classified at a level, receives first goal-oriented study plan.

**Independent Test**: Send `/start` to bot in Telegram, complete full onboarding flow including tech profile and goal selection, verify user record has level + tech_role + goals + study_plan.

### Implementation for User Story 1

- [X] T017 [P] [US1] Implement backend/src/ai/prompts/__init__.py (empty) + backend/src/ai/prompts/assessment.py — Prompt templates for onboarding: WELCOME_MESSAGE (English intro to DevFluent), SELF_DECLARATION_PROMPT (ask user to rate their English), WRITTEN_ASSESSMENT_PROMPTS (3 progressive questions adapted to tech_role: e.g., "Tell me about a project you worked on" for L1, technical scenario for L2+), SPEAKING_ASSESSMENT_PROMPT (ask user to send voice message about a tech topic), CLASSIFICATION_PROMPT (system prompt for LLM to classify level 1-4 from responses, considering tech_role and goals, output JSON with level/cefr/confidence/strengths/weaknesses/feedback_pt/suggested_focus)
- [X] T018 [P] [US1] Implement backend/src/bot/keyboards.py — Builder functions for InlineKeyboard per research R10: `build_tech_role_keyboard()` single-select (Backend, Frontend, Fullstack, Mobile, Data/ML, DevOps/Infra) with callback_data="tech_role:{value}". `build_multi_select_keyboard(category, options, selected)` for tech_stack/goals/target_stack — each button with callback_data="toggle:{category}:{value}", selected items prefixed with "check mark", plus confirm button with callback_data="confirm:{category}". `build_target_company_keyboard()` single-select (Big Tech, Startup, Enterprise, Not sure) with callback_data="target_company:{value}". `build_self_declaration_keyboard()` single-select (Beginner, Intermediate, Advanced)
- [X] T019 [US1] Implement backend/src/core/assessment.py — `AssessmentEngine(db, llm, channel)` with Redis-backed 12-state machine (key `assessment:{user_id}`, 1h TTL). States: WELCOME → SELF_DECLARATION → TECH_ROLE → TECH_STACK → GOALS → TARGET_STACK (conditional: only if "technical_interview" in goals) → TARGET_COMPANY (conditional) → WRITTEN_1 → WRITTEN_2 → WRITTEN_3 (optional) → SPEAKING → CLASSIFYING → DONE. Methods: `start_onboarding(user)` creates assessment conversation + sends welcome. `process_step(user, message, step)` advances state machine — for keyboard steps, read selections from Redis state; for written/speaking, store responses. `save_tech_profile(user, tech_role, tech_stack)` updates user record. `save_goals(user, goals, target_stack, target_company)` updates user record. `classify_level(user, conversation_id)` calls LLM with classification prompt + all responses → returns `AssessmentResult(level, cefr, confidence, strengths, weaknesses, feedback, suggested_focus)` → updates user.current_level + user.onboarding_done=True. Create `@dataclass AssessmentResult` and `@dataclass AssessmentStep(message, keyboard, next_state, is_complete)`
- [X] T020 [US1] Implement backend/src/core/study_plan.py — `StudyPlanGenerator(db, llm)` with `generate(user) -> StudyPlan`. Builds prompt including user.goals, user.target_stack, user.tech_role, user.current_level. Calls LLM chat_json for structured output: theme, focus_skills (list), target_vocab (list). Creates StudyPlan record with level=user.current_level, week_number=1. Focus skills oriented to goals (e.g., "HR interview: self-introduction, strengths/weaknesses" vs "Technical interview: system design vocabulary, AWS terminology")
- [X] T021 [US1] Implement bot command handlers in backend/src/bot/handlers.py — `handle_start(update, context)`: check if user exists → if new, create User(is_active=FALSE) + call assessment.start_onboarding(); if existing + onboarding_done, reply "Welcome back!"; if existing + not done, resume onboarding. `handle_help(update, context)`: list available commands. `handle_callback(update, context)`: parse callback_data → route to assessment.process_step() for onboarding callbacks (tech_role:*, toggle:*, confirm:*, target_company:*, self_declaration:*). `handle_unsupported(update, context)`: reply "I only support text and voice messages for now. Try sending me a text or voice message!"
- [X] T022 [US1] Implement /goals command in backend/src/bot/handlers.py — `handle_goals(update, context)`: if no goals set, prompt to complete onboarding. If goals exist, display current goals/target_stack/target_company with "Edit" button. On edit callback, show multi-select keyboards for goals → conditional target_stack → target_company → save updates via assessment.save_goals() → trigger study_plan.generate() to regenerate plan
- [X] T023 [US1] Register all US1 handlers in backend/src/main.py lifespan — Add to PTB Application: `CommandHandler("start", handle_start)`, `CommandHandler("help", handle_help)`, `CommandHandler("goals", handle_goals)`, `CallbackQueryHandler(handle_callback)`, `MessageHandler(filters.ALL & ~filters.COMMAND & ~filters.TEXT & ~filters.VOICE, handle_unsupported)`. Inject AssessmentEngine and StudyPlanGenerator into handler context via `application.bot_data`

**Checkpoint**: US1 complete — user can /start, complete 5-phase onboarding with tech profile + goals, receive level classification and first study plan. Verify: user record has current_level > 0, onboarding_done=True, tech_role set, goals set, study_plan created.

---

## Phase 4: User Story 2 — Developer Has a First Conversation (Priority: P2)

**Goal**: Activated user sends text messages and receives contextual, level-appropriate AI tutor responses with corrections and vocabulary. Conversations auto-create and context is maintained across messages.

**Independent Test**: Send 3+ text messages to bot after onboarding. Verify responses are coherent, level-appropriate, include corrections when errors present, and reference previous messages in same conversation.

**Depends on**: US1 (user must exist with level and goals)

### Implementation for User Story 2

- [X] T024 [P] [US2] Implement backend/src/ai/prompts/base.py + backend/src/ai/prompts/levels.py — base.py: `SYSTEM_PROMPT_TEMPLATE` with placeholders for {level_name}, {level_instructions}, {user_profile}, {memory_summaries}, {goals_context}. levels.py: `LEVEL_PROMPTS = {1: ..., 2: ..., 3: ..., 4: ...}` — Level 1 (Foundation/A2): simple sentences, explain in Portuguese, speed 0.85. Level 2 (Developing/B1): natural speech, corrections in English, speed 1.0. Level 3 (Proficient/B2): complex topics, tech discussions, speed 1.05. Level 4 (Advanced/C1): idioms, nuance, leadership language, speed 1.10. Each includes persona instructions for the tutor, correction style, vocabulary introduction rate, and goals_context integration (e.g., for interview-prep users, steer conversation toward technical scenarios)
- [X] T025 [US2] Implement backend/src/ai/context.py — `ContextProvider(ABC)` with `async def assemble(user_id, current_message, max_tokens=4000) -> AssembledContext`. `@dataclass AssembledContext: user_profile (str), conversation_history (list[dict]), memory_summaries (list[str]), total_tokens (int)` with `to_system_prompt(base_prompt) -> str` (injects profile + summaries into template) and `to_messages() -> list[dict]` (formats history for OpenAI). `SQLContextProvider(ContextProvider)` implementing 3 layers: Layer 1 (~300 tokens) — user record fields (name, level, tech_role, tech_stack, goals, target_stack, target_company) + top 5 error patterns by occurrence_count. Layer 2 (~2-3K tokens) — last 15 messages from active conversation (query messages by conversation_id ORDER BY created_at). Layer 3 (~500-1K tokens) — last 5 conversation summaries (query conversations WHERE summary IS NOT NULL ORDER BY created_at DESC LIMIT 5). Use tokens.count_tokens() for budget tracking, tokens.truncate_messages() if Layer 2 exceeds budget
- [X] T026 [US2] Implement backend/src/core/feedback.py — `FeedbackAnalyzer(llm)` with `async def extract(ai_response: str, user_message: str) -> FeedbackResult`. Calls LLM chat_json with prompt to extract corrections (original → corrected → explanation) and new vocabulary (word → context → definition) from the tutor response. Returns `@dataclass FeedbackResult: corrections (list[dict]), new_vocab (list[dict])`. Also `async def update_error_patterns(db, user_id, corrections)` — UPSERT into UserErrorPattern: increment occurrence_count if (user_id, error_type, error_detail) exists, else insert
- [X] T027 [US2] Implement backend/src/core/conversation.py — `ConversationEngine(db, llm, context_provider, tts=None)`. `process_message(user, text, is_audio=False, audio_transcription=None) -> ConversationResponse`: (1) find or auto-create conversation (query latest conversation WHERE ended_at IS NULL; if none or last message >30min ago, create new Conversation with mode="free_chat"), (2) save user Message, (3) call context_provider.assemble(), (4) build system prompt from base template + level prompt + context, (5) call llm.chat(), (6) extract feedback via FeedbackAnalyzer, (7) save assistant Message with corrections/tokens_used, (8) if tts provided and is_audio, generate audio, (9) return ConversationResponse(text, audio_bytes, corrections, new_vocab, tokens_used). `end_conversation(conversation_id) -> str`: set ended_at=now(), return conversation_id (summary generated separately by US4)
- [X] T028 [US2] Implement handle_text in backend/src/bot/handlers.py — `handle_text(update, context)`: get user from context.user_data (set by middleware), call conversation_engine.process_message(user, update.message.text), send response text via channel.send_text(). If corrections present, append formatted corrections to response. Catch exceptions: LLM timeout → "I'm having trouble thinking right now. Try again in a moment!", DB error → "Something went wrong on our end. Please try again in a few minutes.", generic → "Oops! Something unexpected happened. Please try again." Log all errors to Sentry with user_id and conversation_id context
- [X] T029 [US2] Register handle_text handler and update DI in backend/src/main.py — Add `MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)` to PTB Application. In lifespan, create SQLContextProvider(async_session), ConversationEngine(session, llm, context_provider) and store in `application.bot_data` for handler access

**Checkpoint**: US2 complete — user can have multi-message text conversations with contextual responses. Verify: conversation auto-created, messages persisted, responses reference prior messages, corrections appear for grammar errors, context stays within token budget.

---

## Phase 5: User Story 3 — Developer Sends a Voice Message (Priority: P3)

**Goal**: User sends voice message, system transcribes via STT, processes through AI tutor, generates text + audio response via TTS, sends both back. Full audio pipeline: Telegram .oga → Groq Whisper → ConversationEngine → OpenAI TTS opus → Telegram send_voice.

**Independent Test**: Send a voice message to bot. Verify bot replies with both text and a voice message. Check transcription stored in message record.

**Depends on**: US2 (ConversationEngine must work for text)

### Implementation for User Story 3

- [X] T030 [P] [US3] Implement backend/src/ai/stt.py — `STTProvider(ABC)` with `async def transcribe(audio_bytes, language="en") -> STTResult`. `@dataclass STTResult: text, language, duration_seconds`. `GroqSTT(STTProvider)` using `groq.AsyncGroq`: `client.audio.transcriptions.create(file=("audio.ogg", audio_bytes), model="whisper-large-v3", language=language)` → extract .text from response. Handle errors: empty transcription → raise, API timeout → raise with descriptive message
- [X] T031 [P] [US3] Implement backend/src/ai/tts.py — `TTSProvider(ABC)` with `async def synthesize(text, speed=1.0, voice="nova") -> bytes`. `OpenAITTS(TTSProvider)` using `openai.AsyncOpenAI`: `client.audio.speech.create(model="gpt-4o-mini-tts", voice=voice, input=text, response_format="opus", speed=speed)` → `.read()` for bytes. Speed varies by level: 0.85 (L1), 1.0 (L2), 1.05 (L3), 1.10 (L4) — caller passes speed based on user.current_level
- [X] T032 [P] [US3] Implement backend/src/utils/audio.py + backend/src/utils/storage.py — audio.py: `download_telegram_audio(bot, file_id) -> bytes` wrapping `bot.get_file()` + `file.download_as_bytearray()`. `upload_audio(storage, user_id, conversation_id, message_id, audio_bytes) -> str` uploading to R2 with key `audio/{user_id}/{conversation_id}/{message_id}.opus`. storage.py: `StorageProvider(ABC)` with `upload(key, data, content_type) -> str` (returns URL) and `download(key) -> bytes`. `R2Storage(StorageProvider)` via boto3 S3-compatible client (endpoint_url from R2 settings). `NullStorage(StorageProvider)` no-op (returns "" for upload, b"" for download). Factory: use R2Storage if R2_ACCOUNT_ID configured, else NullStorage
- [X] T033 [US3] Implement handle_voice in backend/src/bot/handlers.py — `handle_voice(update, context)`: (1) download audio via audio.download_telegram_audio(), (2) transcribe via stt.transcribe(audio_bytes), (3) if transcription empty or too short (<3 chars), reply "I couldn't understand that audio. Could you try again or type your message?", (4) call conversation_engine.process_message(user, transcription, is_audio=True, audio_transcription=transcription), (5) generate TTS audio via tts.synthesize(response.text, speed=LEVEL_SPEEDS[user.current_level]), (6) send text response via channel.send_text(), (7) send audio response via channel.send_audio(), (8) optionally upload both user audio and TTS audio to R2 via storage. Catch STT errors → "I couldn't understand that audio. Could you try again or type your message?"
- [X] T034 [US3] Register handle_voice and update DI in backend/src/main.py — Add `MessageHandler(filters.VOICE, handle_voice)` to PTB Application (BEFORE the TEXT handler). In lifespan, create GroqSTT, OpenAITTS, NullStorage/R2Storage (based on config), update ConversationEngine to receive tts provider. Store STT, TTS, Storage in `application.bot_data`

**Checkpoint**: US3 complete — voice messages work end-to-end. Verify: voice message transcribed, text + audio response sent back, transcription stored in message record, audio optionally uploaded to R2.

---

## Phase 6: User Story 4 — Tutor Remembers Past Sessions (Priority: P4)

**Goal**: When conversations end (30-min timeout or /end), system generates summaries, extracts errors/vocab, tracks patterns. Next conversation, tutor references past sessions via 3-layer context with memory summaries.

**Independent Test**: Have 2+ conversations on separate occasions. In second conversation, verify tutor references topics/errors/vocab from first. Check summary generated, error patterns tracked, vocabulary recorded.

**Depends on**: US2 (ConversationEngine must produce conversations to summarize)

### Implementation for User Story 4

- [X] T035 [US4] Implement backend/src/core/summary.py — `SummaryGenerator(db, llm)` with `async def generate(conversation_id) -> str`: (1) load all messages for conversation, (2) call LLM with summary prompt (extract: 3-4 sentence summary, errors as structured JSON [{type, detail, user_said, correction, severity}], new vocab as [{word, context, definition}]), (3) update conversation.summary, conversation.errors_found, conversation.new_vocab, (4) call feedback.update_error_patterns() for each error, (5) call vocabulary.track_words() for each vocab word, (6) return summary text. Handle edge cases: no messages → skip, LLM failure → log and leave summary NULL
- [X] T036 [US4] Implement backend/src/core/vocabulary.py — `VocabularyTracker(db)` with `async def track_words(user_id, vocab_list: list[dict])`: for each word, UPSERT into UserVocabulary — if exists, increment times_seen; if new, insert with context and level_learned=user.current_level. `async def update_usage(user_id, word)`: increment times_used, recalculate next_review using SM-2 simplified: `intervals = [1, 3, 7, 14, 30, 60]`, `next_review = now + intervals[min(times_used, 5)] * ease_factor`. `async def get_due_words(user_id, limit=10) -> list[UserVocabulary]`: query WHERE next_review <= now() ORDER BY next_review LIMIT
- [X] T037 [US4] Enhance backend/src/ai/context.py — Update SQLContextProvider.assemble() Layer 3 implementation: query last 5 conversations WHERE summary IS NOT NULL ORDER BY created_at DESC for user_id. Format summaries as list of strings. Update Layer 1 to include top 5 UserErrorPattern entries formatted as "Recurring errors: {error_type} - {error_detail} ({occurrence_count}x)". Update AssembledContext.to_system_prompt() to inject memory_summaries section and error patterns into the system prompt template. Verify total_tokens stays within max_tokens budget
- [X] T038 [US4] Implement /end command and conversation timeout in backend/src/bot/handlers.py — `handle_end(update, context)`: find active conversation for user (ended_at IS NULL), if none reply "No active conversation to end.", else call conversation_engine.end_conversation(conversation_id) then summary_generator.generate(conversation_id), reply "Session saved! Here's a summary: {summary}". Conversation timeout: in handle_text/handle_voice, before creating new conversation, check if previous conversation's last message is >CONVERSATION_TIMEOUT_MIN ago → if so, auto-end that conversation + generate summary before creating new one
- [X] T039 [US4] Register /end handler in backend/src/main.py — Add `CommandHandler("end", handle_end)` to PTB Application. In lifespan, create SummaryGenerator and VocabularyTracker, store in `application.bot_data` for handler access

**Checkpoint**: US4 complete — memory system works end-to-end. Verify: /end generates summary, auto-timeout generates summary, second conversation references first session's details, error patterns accumulated across sessions, vocabulary tracked with SM-2 scheduling.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Admin features, remaining commands, deployment, and testing

### Admin & Remaining Commands

- [X] T040 [P] Implement backend/src/services/billing.py — Admin command handlers (check ADMIN_TELEGRAM_ID): `handle_activate(update, context)`: parse telegram_id from `/activate <tid>`, set User.is_active=True + subscription="active". `handle_deactivate(update, context)`: set is_active=False + subscription="inactive". `handle_users(update, context)`: list all users with name, level, is_active, onboarding_done. `handle_stats(update, context)`: count users, active users, total messages today, estimated cost (messages * ~R$0.21)
- [X] T041 [P] Implement backend/src/ai/prompts/interview.py + backend/src/core/mock_interview.py — interview.py: MOCK_INTERVIEW_PROMPTS by type (hr_behavioral, technical_screening, system_design) with role-play instructions for interviewer persona. mock_interview.py: `MockInterviewEngine(db, llm, channel)` with `start_interview(user, interview_type=None) -> Conversation`: if type not specified, auto-suggest based on user.goals (technical_interview → technical_screening, hr_interview → hr_behavioral). Creates conversation with mode="mock_interview". `process_response(user, text) -> str`: continue interview flow, track questions asked, provide feedback at end
- [X] T042 [P] Implement backend/src/services/reports.py + backend/src/services/notifications.py — reports.py: `ReportService(db, channel)` with `generate_weekly_report(user_id) -> str`: query WeeklyMetrics, format as message with minutes_practiced, messages_sent, words learned, streak, progress toward weekly_goal_min. notifications.py: `NotificationService(db, channel, scheduler)` using APScheduler: daily reminder at user.timezone 19:00 if no messages today, weekly report every Monday 09:00. Register scheduler in main.py lifespan
- [X] T043 Implement remaining bot commands in backend/src/bot/handlers.py — `handle_level(update, context)`: show current_level, cefr_estimate, progress info. `handle_plan(update, context)`: show active StudyPlan (theme, focus_skills, target_vocab). `handle_interview(update, context)`: auto-suggest interview type based on goals, start mock_interview. `handle_report(update, context)`: trigger ReportService.generate_weekly_report(). Register ALL new CommandHandlers in main.py including: /level, /plan, /interview, /report, plus admin commands from T040 (/activate, /deactivate, /users, /stats with ADMIN_TELEGRAM_ID guard)

### DevOps & Deployment

- [X] T044 [P] Create backend/Dockerfile — Base: python:3.12-slim, install ffmpeg, COPY backend/, pip install, CMD: `sh -c "alembic upgrade head && uvicorn backend.src.main:app --host 0.0.0.0 --port ${PORT:-8000}"`. Create railway.toml with `[build] builder = "dockerfile" dockerfilePath = "backend/Dockerfile"`. Create docker-compose.yml at repo root for local dev: PostgreSQL 16 (port 5432, user/pass devfluent), Redis 7 (port 6379)
- [X] T045 [P] Create .github/workflows/ci.yml — Trigger on push/PR. Jobs: lint (ruff check backend/src/), test (pytest backend/tests/ -v with PostgreSQL service container), deploy-on-main (railway deploy or just tag for manual deploy)

### Testing

- [X] T046 Implement backend/tests/conftest.py — Async pytest fixtures: `db_engine` (in-memory SQLite or test PostgreSQL), `db_session` (async session with transaction rollback), `mock_llm` (MockLLMProvider returning canned responses), `mock_stt` (MockSTTProvider), `mock_tts` (MockTTSProvider returning b"fake_audio"), `mock_channel` (MockMessageChannel recording sent messages), `test_user` (User fixture with default values + tech_role="fullstack" + goals=["technical_interview"]). All mocks implement the ABCs — no external API calls in tests
- [X] T047 [P] Implement test files — backend/tests/test_conversation.py: test process_message returns response, test auto-create conversation, test context maintained across messages, test error handling for LLM timeout. backend/tests/test_assessment.py: test onboarding state machine transitions (WELCOME → ... → DONE), test save_tech_profile, test save_goals with conditional target_stack, test classify_level returns valid AssessmentResult. backend/tests/test_context.py: test 3-layer assembly, test token budget not exceeded (use count_tokens to verify), test truncation when history too long. backend/tests/test_prompts.py: test all prompt templates render without errors, test level prompts include expected instructions, test assessment prompts include tech_role placeholder. backend/tests/test_interview.py: test mock interview auto-suggests based on goals, test interview conversation flow

### Scripts & Validation

- [X] T048 [P] Create backend/scripts/seed_vocab.py (base vocabulary by level: L1=50 common tech words, L2=100 intermediate, L3=150 advanced, L4=200 fluent-level) + backend/scripts/create_test_user.py (create User with telegram_id from .env ADMIN_TELEGRAM_ID, is_active=True, onboarding_done=True, current_level=2, tech_role="fullstack", goals=["technical_interview", "meetings"], target_stack=["node", "aws"])
- [X] T049 Run quickstart.md end-to-end validation — Follow all 9 steps from quickstart.md: install deps, start docker compose, configure .env, run migrations, start server, verify /health, set up ngrok webhook, send /start to bot. Document any fixes needed

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user stories
- **Phase 3 (US1)**: Depends on Phase 2 — MVP starting point
- **Phase 4 (US2)**: Depends on Phase 2 + Phase 3 (user must exist with level/goals)
- **Phase 5 (US3)**: Depends on Phase 4 (ConversationEngine must work)
- **Phase 6 (US4)**: Depends on Phase 4 (conversations must exist to summarize)
- **Phase 7 (Polish)**: Depends on Phase 6 (all user stories complete)

### User Story Dependencies

```
Phase 1 → Phase 2 → US1 (P1) → US2 (P2) → US3 (P3)
                                           ↘ US4 (P4)
                                    → Polish
```

- **US1 → US2**: Sequential (user needs level + goals for conversation context)
- **US2 → US3**: Sequential (voice extends text conversation flow)
- **US2 → US4**: Sequential (summaries generated from conversations)
- **US3 ↔ US4**: Can run in parallel after US2 (independent features)

### Within Each User Story

1. Prompt templates and keyboard builders first ([P] — parallel)
2. Core engines/services (depend on prompts)
3. Bot handlers (depend on engines)
4. Handler registration in main.py (depends on handlers)

### Parallel Opportunities

**Phase 2** (after T004 config + T005 database):
```
T006 models/base.py  ─┐
T007 ai/llm.py        │ All [P] — different files, no cross-dependencies
T008 channels/base.py │
T009 utils/tokens.py  ─┘
```
Then (after T006 base.py):
```
T010 models/user.py         ─┐
T011 models/conversation.py  │ All [P] — each model depends only on base.py
T012 remaining models        ─┘
```

**Phase 3 US1** (T017 + T018 in parallel, then T019-T023 sequential):
```
T017 prompts/assessment.py ─┐
T018 keyboards.py          ─┘ [P] then → T019 AssessmentEngine → T020 StudyPlan → T021-T023
```

**Phase 5 US3** (T030-T032 all [P], then T033-T034 sequential):
```
T030 ai/stt.py       ─┐
T031 ai/tts.py        │ All [P] — independent provider abstractions
T032 audio + storage  ─┘ then → T033 handle_voice → T034 register
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1: Setup (3 tasks)
2. Complete Phase 2: Foundational (13 tasks)
3. Complete Phase 3: US1 — Developer Starts the Bot (7 tasks)
4. **STOP and VALIDATE**: /start → onboarding → level + study plan
5. Deploy if ready (bot responds to /start, creates users, classifies levels)

### Full MVP (US1 + US2)

6. Complete Phase 4: US2 — First Conversation (6 tasks)
7. **VALIDATE**: Multi-message conversation with context, corrections, goal-adapted prompts

### Complete Product (All Stories)

8. Complete Phase 5: US3 — Voice Messages (5 tasks) — can parallel with US4
9. Complete Phase 6: US4 — Memory/Summaries (5 tasks) — can parallel with US3
10. Complete Phase 7: Polish (10 tasks) — admin, deployment, tests

### Incremental Delivery

| Milestone | Stories | Tasks | What's Testable |
|-----------|---------|-------|-----------------|
| Foundation | — | T001-T016 | /health returns 200, webhook receives updates |
| MVP Bot | US1 | T017-T023 | /start → onboarding → level + plan |
| Conversational | US1+US2 | T024-T029 | Text conversations with AI tutor |
| Voice | US1-US3 | T030-T034 | Voice messages transcribed + TTS response |
| Memory | US1-US4 | T035-T039 | Cross-session memory + summaries |
| Production | All | T040-T049 | Admin, deployment, tests, scripts |

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- Each checkpoint validates that story works independently before proceeding
- Constitution VII (Test-Driven Quality) satisfied by Phase 7 test suite
- Constitution III (Provider Abstraction) enforced: core/ MUST NOT import concrete providers
- All paths use `backend/src/` prefix per constitution v2.0.0 repository structure
- Commit after each task or logical group of [P] tasks
- Total: 49 tasks across 7 phases
