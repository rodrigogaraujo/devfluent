from contextlib import asynccontextmanager

import sentry_sdk
import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from backend.src.ai.context import SQLContextProvider
from backend.src.ai.llm import OpenAILLM
from backend.src.ai.stt import GroqSTT
from backend.src.ai.tts import OpenAITTS
from backend.src.bot.handlers import (
    handle_callback,
    handle_end,
    handle_goals,
    handle_help,
    handle_interview,
    handle_level,
    handle_plan,
    handle_report,
    handle_start,
    handle_text,
    handle_unsupported,
    handle_voice,
)
from backend.src.channels.telegram import TelegramChannel
from backend.src.config import settings
from backend.src.core.assessment import AssessmentEngine
from backend.src.core.conversation import ConversationEngine
from backend.src.core.feedback import FeedbackAnalyzer
from backend.src.core.mock_interview import MockInterviewEngine
from backend.src.core.study_plan import StudyPlanGenerator
from backend.src.core.summary import SummaryGenerator
from backend.src.core.vocabulary import VocabularyTracker
from backend.src.database import async_session, engine
from backend.src.services.billing import handle_activate, handle_deactivate, handle_stats, handle_users
from backend.src.utils.storage import create_storage

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---

    # Sentry
    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            traces_sample_rate=0.1,
            enable_tracing=True,
        )
        logger.info("sentry_initialized")

    # Structlog configuration
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer() if settings.SENTRY_DSN == "" else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # PTB Application
    ptb_app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    await ptb_app.initialize()

    # Set webhook
    webhook_url = f"{settings.TELEGRAM_WEBHOOK_URL}/webhook/telegram"
    await ptb_app.bot.set_webhook(url=webhook_url)
    logger.info("webhook_set", url=webhook_url)

    # Providers
    llm = OpenAILLM(api_key=settings.OPENAI_API_KEY)
    channel = TelegramChannel(bot=ptb_app.bot)
    stt = GroqSTT(api_key=settings.GROQ_API_KEY)
    tts = OpenAITTS(api_key=settings.OPENAI_API_KEY)
    storage = create_storage(
        account_id=settings.R2_ACCOUNT_ID,
        access_key=settings.R2_ACCESS_KEY,
        secret_key=settings.R2_SECRET_KEY,
        bucket=settings.R2_BUCKET,
        public_url=settings.R2_PUBLIC_URL,
    )

    # Redis (optional)
    redis_client = None
    if settings.REDIS_URL:
        try:
            import redis.asyncio as aioredis

            redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            await redis_client.ping()
            logger.info("redis_connected")
        except Exception:
            logger.warning("redis_connection_failed")
            redis_client = None

    # Core services — db=None, handlers inject per-request session
    assessment_engine = AssessmentEngine(
        db=None, llm=llm, channel=channel, redis_client=redis_client
    )
    study_plan_generator = StudyPlanGenerator(db=None, llm=llm)

    context_provider = SQLContextProvider(session_factory=async_session)
    feedback_analyzer = FeedbackAnalyzer(llm=llm)
    conversation_engine = ConversationEngine(
        db=None,
        llm=llm,
        context_provider=context_provider,
        feedback_analyzer=feedback_analyzer,
        tts=tts,
    )
    summary_generator = SummaryGenerator(db=None, llm=llm)
    vocabulary_tracker = VocabularyTracker(db=None)
    mock_interview_engine = MockInterviewEngine(db=None, llm=llm, channel=channel)

    # Store in bot_data for handler access
    ptb_app.bot_data["db_session"] = async_session
    ptb_app.bot_data["llm"] = llm
    ptb_app.bot_data["channel"] = channel
    ptb_app.bot_data["redis"] = redis_client
    ptb_app.bot_data["stt"] = stt
    ptb_app.bot_data["tts"] = tts
    ptb_app.bot_data["storage"] = storage
    ptb_app.bot_data["assessment_engine"] = assessment_engine
    ptb_app.bot_data["study_plan_generator"] = study_plan_generator
    ptb_app.bot_data["context_provider"] = context_provider
    ptb_app.bot_data["feedback_analyzer"] = feedback_analyzer
    ptb_app.bot_data["conversation_engine"] = conversation_engine
    ptb_app.bot_data["summary_generator"] = summary_generator
    ptb_app.bot_data["vocabulary_tracker"] = vocabulary_tracker
    ptb_app.bot_data["mock_interview_engine"] = mock_interview_engine

    # Register handlers (order matters — most specific first)
    # User commands
    ptb_app.add_handler(CommandHandler("start", handle_start))
    ptb_app.add_handler(CommandHandler("help", handle_help))
    ptb_app.add_handler(CommandHandler("goals", handle_goals))
    ptb_app.add_handler(CommandHandler("end", handle_end))
    ptb_app.add_handler(CommandHandler("level", handle_level))
    ptb_app.add_handler(CommandHandler("plan", handle_plan))
    ptb_app.add_handler(CommandHandler("interview", handle_interview))
    ptb_app.add_handler(CommandHandler("report", handle_report))

    # Admin commands
    ptb_app.add_handler(CommandHandler("activate", handle_activate))
    ptb_app.add_handler(CommandHandler("deactivate", handle_deactivate))
    ptb_app.add_handler(CommandHandler("users", handle_users))
    ptb_app.add_handler(CommandHandler("stats", handle_stats))

    # Message handlers
    ptb_app.add_handler(CallbackQueryHandler(handle_callback))
    ptb_app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    ptb_app.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND & ~filters.TEXT & ~filters.VOICE,
            handle_unsupported,
        )
    )

    # Store in app state
    app.state.ptb_app = ptb_app
    app.state.llm = llm
    app.state.channel = channel
    app.state.redis = redis_client
    app.state.db_session = async_session

    logger.info("startup_complete")
    yield

    # --- Shutdown ---
    try:
        await ptb_app.bot.delete_webhook()
    except Exception:
        pass
    await ptb_app.shutdown()
    await engine.dispose()
    if redis_client:
        await redis_client.aclose()
    logger.info("shutdown_complete")


app = FastAPI(title="DevFluent", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health():
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok", "version": "0.1.0"}
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "error": "database_unavailable"},
        )


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        ptb_app: Application = request.app.state.ptb_app
        update = Update.de_json(data, ptb_app.bot)
        if update:
            await ptb_app.process_update(update)
    except Exception:
        logger.exception("webhook_processing_error")
    return JSONResponse(content={}, status_code=200)
