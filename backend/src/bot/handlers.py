import structlog
from telegram import Update
from telegram.ext import ContextTypes

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from backend.src.ai.prompts.levels import get_level_config
from backend.src.ai.stt import STTProvider
from backend.src.ai.tts import TTSProvider
from backend.src.bot.middleware import active_check, rate_limit, user_lookup
from backend.src.core.assessment import AssessmentEngine
from backend.src.core.conversation import ConversationEngine
from backend.src.core.mock_interview import MockInterviewEngine
from backend.src.core.study_plan import StudyPlanGenerator
from backend.src.core.summary import SummaryGenerator
from backend.src.core.vocabulary import VocabularyTracker
from backend.src.models.user import User
from backend.src.services.reports import ReportService
from backend.src.utils.audio import download_telegram_audio

logger = structlog.get_logger()

HELP_TEXT = (
    "Here's what I can do:\n\n"
    "/start — Start onboarding or restart\n"
    "/help — Show this help message\n"
    "/goals — View or edit your learning goals\n"
    "/level — Show your current level\n"
    "/plan — Show your weekly study plan\n"
    "/interview — Start a mock interview\n"
    "/report — View your weekly report\n"
    "/end — End current conversation and save summary"
)


async def _run_middleware(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> User | None:
    app = context.application
    db_session = app.bot_data["db_session"]()

    user = await user_lookup(update, context, db_session)
    if user is None:
        return None

    context.user_data["db_session_instance"] = db_session
    return user


async def _commit_session(context: ContextTypes.DEFAULT_TYPE) -> None:
    db_session = context.user_data.get("db_session_instance")
    if db_session:
        try:
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise
        finally:
            await db_session.close()


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        user = await _run_middleware(update, context)
        if user is None or update.effective_chat is None:
            return

        chat_id = str(update.effective_chat.id)
        app = context.application
        db_session = context.user_data["db_session_instance"]

        assessment: AssessmentEngine = app.bot_data["assessment_engine"]
        study_plan_gen: StudyPlanGenerator = app.bot_data["study_plan_generator"]

        # Replace assessment engine's db session with current one
        assessment._db = db_session
        study_plan_gen._db = db_session

        print(f"[START] user={user.name} (id={user.id}) onboarding_done={user.onboarding_done}")

        if user.onboarding_done:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=(
                    f"Welcome back, {user.name}! "
                    "You're all set. Just send me a message to practice English.\n\n"
                    "Use /help to see all available commands."
                ),
            )
        else:
            # Check if there's an active onboarding
            state = await assessment.get_onboarding_state(user.id)
            if state and assessment.is_onboarding_active(state):
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="Let's continue your onboarding! Please respond to the previous question.",
                )
            else:
                await assessment.start_onboarding(user, chat_id)

        await _commit_session(context)
    except Exception:
        logger.exception("handle_start_error")
        if update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Oops! Something unexpected happened. Please try again.",
            )


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=HELP_TEXT,
        )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return

    await query.answer()

    try:
        user = await _run_middleware(update, context)
        if user is None or update.effective_chat is None:
            return

        chat_id = str(update.effective_chat.id)
        callback_data = query.data or ""
        print(f"[CALLBACK] user={user.name} (id={user.id}) data={callback_data}")
        app = context.application
        db_session = context.user_data["db_session_instance"]

        assessment: AssessmentEngine = app.bot_data["assessment_engine"]
        study_plan_gen: StudyPlanGenerator = app.bot_data["study_plan_generator"]
        assessment._db = db_session
        study_plan_gen._db = db_session

        # Check for active rate limit
        redis_client = app.bot_data.get("redis")
        if not await rate_limit(update, context, redis_client):
            await _commit_session(context)
            return

        # Route onboarding callbacks
        onboarding_prefixes = (
            "self_declaration:", "tech_role:", "toggle:", "confirm:", "target_company:",
        )
        if any(callback_data.startswith(p) for p in onboarding_prefixes):
            await assessment.process_callback(user, chat_id, callback_data)

            # If onboarding just completed, generate study plan
            state = await assessment.get_onboarding_state(user.id)
            if state and state.state == "done":
                await study_plan_gen.generate(user)

        # Goals editing callbacks
        elif callback_data.startswith("edit_goals"):
            from backend.src.bot.keyboards import build_goals_keyboard

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Select your updated goals:",
                reply_markup=build_goals_keyboard(set(user.goals)),
            )

        # Interview type selection
        elif callback_data.startswith("interview:"):
            interview_type = callback_data.split(":", 1)[1]
            interview_engine: MockInterviewEngine = app.bot_data["mock_interview_engine"]
            interview_engine._db = db_session
            await interview_engine.start_interview(user, chat_id, interview_type)

        await _commit_session(context)
    except Exception:
        logger.exception("handle_callback_error")
        if update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Oops! Something unexpected happened. Please try again.",
            )


async def handle_unsupported(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="I only support text and voice messages for now. Try sending me a text or voice message!",
        )


async def handle_onboarding_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """Process text messages during onboarding. Returns True if handled."""
    user: User | None = context.user_data.get("user")
    if user is None or user.onboarding_done:
        return False

    app = context.application
    assessment: AssessmentEngine = app.bot_data["assessment_engine"]

    state = await assessment.get_onboarding_state(user.id)
    if state is None or not assessment.is_onboarding_active(state):
        return False

    # Only handle text during written assessment phases
    if state.state not in ("written_1", "written_2", "written_3"):
        return False

    chat_id = str(update.effective_chat.id) if update.effective_chat else ""
    if not chat_id:
        return False

    db_session = context.user_data.get("db_session_instance")
    if db_session:
        assessment._db = db_session

    study_plan_gen: StudyPlanGenerator = app.bot_data["study_plan_generator"]
    if db_session:
        study_plan_gen._db = db_session

    text = update.message.text if update.message else ""
    if not text:
        return False

    await assessment.process_text_response(user, chat_id, text)

    # Check if we need to handle voice next or if done
    state = await assessment.get_onboarding_state(user.id)
    if state and state.state == "done":
        await study_plan_gen.generate(user)

    return True


async def handle_onboarding_voice(
    update: Update, context: ContextTypes.DEFAULT_TYPE, transcription: str
) -> bool:
    """Process voice messages during onboarding. Returns True if handled."""
    user: User | None = context.user_data.get("user")
    if user is None or user.onboarding_done:
        return False

    app = context.application
    assessment: AssessmentEngine = app.bot_data["assessment_engine"]

    state = await assessment.get_onboarding_state(user.id)
    if state is None or state.state != "speaking":
        return False

    chat_id = str(update.effective_chat.id) if update.effective_chat else ""
    if not chat_id:
        return False

    db_session = context.user_data.get("db_session_instance")
    if db_session:
        assessment._db = db_session

    study_plan_gen: StudyPlanGenerator = app.bot_data["study_plan_generator"]
    if db_session:
        study_plan_gen._db = db_session

    await assessment.process_voice_response(user, chat_id, transcription)

    # Generate study plan after classification
    state = await assessment.get_onboarding_state(user.id)
    if state and state.state == "done":
        await study_plan_gen.generate(user)

    return True


async def handle_goals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        user = await _run_middleware(update, context)
        if user is None or update.effective_chat is None:
            return

        if not await active_check(update, context):
            await _commit_session(context)
            return

        chat_id = update.effective_chat.id

        if not user.onboarding_done:
            await context.bot.send_message(
                chat_id=chat_id,
                text="Please complete onboarding first with /start to set your goals.",
            )
            await _commit_session(context)
            return

        # Format current goals
        goals_map = {
            "hr_interview": "HR/Behavioral interview",
            "technical_interview": "Technical interview",
            "meetings": "Daily meetings & standups",
            "presentations": "Leading meetings & presentations",
        }
        goals_display = [goals_map.get(g, g) for g in (user.goals or [])]

        lines = [f"Your current learning goals:\n"]
        if goals_display:
            for g in goals_display:
                lines.append(f"  - {g}")
        else:
            lines.append("  (none set)")

        if user.target_stack:
            lines.append(f"\nTarget stack: {', '.join(user.target_stack)}")
        if user.target_company:
            lines.append(f"Target company: {user.target_company}")
        if user.tech_role:
            lines.append(f"Tech role: {user.tech_role}")

        lines.append("\nWant to update your goals?")

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(text="Edit Goals", callback_data="edit_goals")]
        ])

        await context.bot.send_message(
            chat_id=chat_id,
            text="\n".join(lines),
            reply_markup=keyboard,
        )

        await _commit_session(context)
    except Exception:
        logger.exception("handle_goals_error")
        if update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Oops! Something unexpected happened. Please try again.",
            )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        user = await _run_middleware(update, context)
        if user is None or update.effective_chat is None:
            return

        if not await active_check(update, context):
            await _commit_session(context)
            return

        app = context.application
        db_session = context.user_data["db_session_instance"]

        redis_client = app.bot_data.get("redis")
        if not await rate_limit(update, context, redis_client):
            await _commit_session(context)
            return

        # Check if user is in onboarding — route to onboarding handler
        if not user.onboarding_done:
            handled = await handle_onboarding_text(update, context)
            if handled:
                await _commit_session(context)
                return

        text = update.message.text if update.message else ""
        if not text:
            await _commit_session(context)
            return

        print(f"[CONV] user={user.name} (id={user.id}) input: {text[:200]}")

        conversation_engine: ConversationEngine = app.bot_data["conversation_engine"]
        conversation_engine._db = db_session

        response = await conversation_engine.process_message(user, text)

        print(f"[CONV] bot response: {response.text[:200]}")
        if response.corrections:
            print(f"[CONV] corrections: {response.corrections}")
        if response.new_vocab:
            print(f"[CONV] new_vocab: {response.new_vocab}")

        # Send voice response first (main interaction)
        if response.audio_bytes:
            await context.bot.send_voice(
                chat_id=update.effective_chat.id,
                voice=response.audio_bytes,
            )

        # Build text response with corrections/vocab
        reply_parts = []

        if response.corrections:
            corrections_text = "📝 <b>Corrections:</b>"
            for c in response.corrections[:3]:
                original = c.get("original", "")
                corrected = c.get("corrected", "")
                explanation = c.get("explanation", "")
                corrections_text += f"\n• <i>{original}</i> → <b>{corrected}</b>"
                if explanation:
                    corrections_text += f" ({explanation})"
            reply_parts.append(corrections_text)

        if response.new_vocab:
            vocab_text = "📚 <b>New vocabulary:</b>"
            for v in response.new_vocab[:2]:
                word = v.get("word", "")
                definition = v.get("definition", "")
                vocab_text += f"\n• <b>{word}</b>: {definition}"
            reply_parts.append(vocab_text)

        # Send text with corrections only if there are corrections/vocab, otherwise send text as caption-like message
        if reply_parts:
            full_reply = "\n\n".join(reply_parts)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=full_reply,
                parse_mode="HTML",
            )
        elif not response.audio_bytes:
            # Fallback: no TTS available, send text
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=response.text,
            )

        await _commit_session(context)

    except TimeoutError:
        logger.exception("handle_text_timeout")
        if update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="I'm having trouble thinking right now. Try again in a moment!",
            )
    except Exception:
        logger.exception("handle_text_error")
        if update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Oops! Something unexpected happened. Please try again.",
            )


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        user = await _run_middleware(update, context)
        if user is None or update.effective_chat is None:
            return

        if not await active_check(update, context):
            await _commit_session(context)
            return

        app = context.application
        db_session = context.user_data["db_session_instance"]

        redis_client = app.bot_data.get("redis")
        if not await rate_limit(update, context, redis_client):
            await _commit_session(context)
            return

        # Download audio from Telegram
        voice = update.message.voice if update.message else None
        if voice is None:
            await _commit_session(context)
            return

        audio_bytes = await download_telegram_audio(context.bot, voice.file_id)

        # Transcribe via STT
        stt: STTProvider | None = app.bot_data.get("stt")
        if stt is None:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Voice messages are not available right now. Please type your message instead.",
            )
            await _commit_session(context)
            return

        try:
            stt_result = await stt.transcribe(audio_bytes)
        except Exception:
            logger.warning("stt_transcription_failed", user_id=str(user.id))
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="I couldn't understand that audio. Could you try again or type your message?",
            )
            await _commit_session(context)
            return

        transcription = stt_result.text
        print(f"[CONV] user={user.name} (id={user.id}) voice transcription: {transcription[:200]}")
        if len(transcription) < 3:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="I couldn't understand that audio. Could you try again or type your message?",
            )
            await _commit_session(context)
            return

        # Check if user is in onboarding speaking phase
        if not user.onboarding_done:
            handled = await handle_onboarding_voice(update, context, transcription)
            if handled:
                await _commit_session(context)
                return

        # Process through conversation engine
        conversation_engine: ConversationEngine = app.bot_data["conversation_engine"]
        conversation_engine._db = db_session

        response = await conversation_engine.process_message(
            user, transcription, is_audio=True, audio_transcription=transcription
        )

        print(f"[CONV] bot response: {response.text[:200]}")
        if response.corrections:
            print(f"[CONV] corrections: {response.corrections}")
        if response.new_vocab:
            print(f"[CONV] new_vocab: {response.new_vocab}")

        # Build text response with corrections
        reply_parts = [response.text]

        if response.corrections:
            corrections_text = "\n\n\U0001f4dd <b>Corrections:</b>"
            for c in response.corrections[:3]:
                original = c.get("original", "")
                corrected = c.get("corrected", "")
                explanation = c.get("explanation", "")
                corrections_text += f"\n\u2022 <i>{original}</i> \u2192 <b>{corrected}</b>"
                if explanation:
                    corrections_text += f" ({explanation})"
            reply_parts.append(corrections_text)

        if response.new_vocab:
            vocab_text = "\n\n\U0001f4da <b>New vocabulary:</b>"
            for v in response.new_vocab[:2]:
                word = v.get("word", "")
                definition = v.get("definition", "")
                vocab_text += f"\n\u2022 <b>{word}</b>: {definition}"
            reply_parts.append(vocab_text)

        full_reply = "".join(reply_parts)

        # Send text response
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=full_reply,
            parse_mode="HTML",
        )

        # Send audio response if TTS available
        tts: TTSProvider | None = app.bot_data.get("tts")
        if tts is not None:
            try:
                level_config = get_level_config(user.current_level)
                audio_response = await tts.synthesize(
                    response.text, speed=level_config.tts_speed
                )
                await context.bot.send_voice(
                    chat_id=update.effective_chat.id,
                    voice=audio_response,
                )
            except Exception:
                logger.warning("tts_synthesis_failed", user_id=str(user.id))

        await _commit_session(context)

    except TimeoutError:
        logger.exception("handle_voice_timeout")
        if update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="I'm having trouble thinking right now. Try again in a moment!",
            )
    except Exception:
        logger.exception("handle_voice_error")
        if update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Oops! Something unexpected happened. Please try again.",
            )


async def handle_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        user = await _run_middleware(update, context)
        if user is None or update.effective_chat is None:
            return

        if not await active_check(update, context):
            await _commit_session(context)
            return

        chat_id = update.effective_chat.id
        app = context.application
        db_session = context.user_data["db_session_instance"]

        conversation_engine: ConversationEngine = app.bot_data["conversation_engine"]
        conversation_engine._db = db_session

        summary_gen: SummaryGenerator = app.bot_data["summary_generator"]
        summary_gen._db = db_session

        vocab_tracker: VocabularyTracker = app.bot_data["vocabulary_tracker"]
        vocab_tracker._db = db_session

        # Find active conversation
        from sqlalchemy import select

        from backend.src.models.conversation import Conversation

        result = await db_session.execute(
            select(Conversation)
            .where(
                Conversation.user_id == user.id,
                Conversation.ended_at.is_(None),
                Conversation.mode != "onboarding",
            )
            .order_by(Conversation.created_at.desc())
            .limit(1)
        )
        conversation = result.scalar_one_or_none()

        if conversation is None:
            await context.bot.send_message(
                chat_id=chat_id,
                text="No active conversation to end.",
            )
            await _commit_session(context)
            return

        # End conversation
        await conversation_engine.end_conversation(conversation.id)

        # Generate summary
        summary = await summary_gen.generate(conversation.id)

        # Track vocabulary from conversation
        if conversation.new_vocab:
            await vocab_tracker.track_words(user.id, conversation.new_vocab)

        if summary:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"Session saved! Here's a summary:\n\n{summary}",
            )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text="Session ended and saved!",
            )

        await _commit_session(context)

    except Exception:
        logger.exception("handle_end_error")
        if update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Oops! Something unexpected happened. Please try again.",
            )


async def handle_level(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        user = await _run_middleware(update, context)
        if user is None or update.effective_chat is None:
            return

        if not await active_check(update, context):
            await _commit_session(context)
            return

        if not user.onboarding_done:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Please complete onboarding first with /start.",
            )
            await _commit_session(context)
            return

        level_config = get_level_config(user.current_level)
        text = (
            f"<b>Your English Level</b>\n\n"
            f"Level: {user.current_level} — {level_config.name}\n"
            f"CEFR: {user.cefr_estimate or level_config.cefr}\n"
            f"TTS speed: {level_config.tts_speed}x\n\n"
            f"Keep practicing to level up!"
        )

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            parse_mode="HTML",
        )
        await _commit_session(context)
    except Exception:
        logger.exception("handle_level_error")
        if update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Oops! Something unexpected happened. Please try again.",
            )


async def handle_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        user = await _run_middleware(update, context)
        if user is None or update.effective_chat is None:
            return

        if not await active_check(update, context):
            await _commit_session(context)
            return

        if not user.onboarding_done:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Please complete onboarding first with /start.",
            )
            await _commit_session(context)
            return

        db_session = context.user_data["db_session_instance"]

        from sqlalchemy import select

        from backend.src.models.study_plan import StudyPlan

        result = await db_session.execute(
            select(StudyPlan)
            .where(StudyPlan.user_id == user.id, StudyPlan.completed.is_(False))
            .order_by(StudyPlan.week_number.desc())
            .limit(1)
        )
        plan = result.scalar_one_or_none()

        if plan is None:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="No active study plan found. Complete onboarding to generate one.",
            )
            await _commit_session(context)
            return

        skills = plan.focus_skills or []
        vocab = plan.target_vocab or []

        lines = [
            f"<b>Study Plan — Week {plan.week_number}</b>\n",
            f"Theme: {plan.theme or 'General practice'}",
            "",
            "<b>Focus skills:</b>",
        ]
        for s in skills:
            lines.append(f"  - {s}")

        if vocab:
            lines.append("\n<b>Target vocabulary:</b>")
            for v in vocab:
                lines.append(f"  - {v}")

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="\n".join(lines),
            parse_mode="HTML",
        )
        await _commit_session(context)
    except Exception:
        logger.exception("handle_plan_error")
        if update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Oops! Something unexpected happened. Please try again.",
            )


async def handle_interview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        user = await _run_middleware(update, context)
        if user is None or update.effective_chat is None:
            return

        if not await active_check(update, context):
            await _commit_session(context)
            return

        if not user.onboarding_done:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Please complete onboarding first with /start.",
            )
            await _commit_session(context)
            return

        app = context.application
        db_session = context.user_data["db_session_instance"]

        interview_engine: MockInterviewEngine = app.bot_data["mock_interview_engine"]
        interview_engine._db = db_session

        chat_id = str(update.effective_chat.id)
        suggested = interview_engine.suggest_interview_type(user)

        type_labels = {
            "hr_behavioral": "HR/Behavioral",
            "technical_screening": "Technical Screening",
            "system_design": "System Design",
        }

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    text=f"{label} {'(suggested)' if t == suggested else ''}".strip(),
                    callback_data=f"interview:{t}",
                )
            ]
            for t, label in type_labels.items()
        ])

        target_info = ""
        if user.target_stack:
            target_info = f"\nBased on your goals, I'd suggest a <b>{type_labels.get(suggested, suggested)}</b> interview."

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Let's practice a mock interview!{target_info}\n\nChoose the type:",
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        await _commit_session(context)
    except Exception:
        logger.exception("handle_interview_error")
        if update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Oops! Something unexpected happened. Please try again.",
            )


async def handle_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        user = await _run_middleware(update, context)
        if user is None or update.effective_chat is None:
            return

        if not await active_check(update, context):
            await _commit_session(context)
            return

        db_session = context.user_data["db_session_instance"]
        report_service = ReportService(db=db_session)
        report = await report_service.generate_weekly_report(user.id)

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=report,
        )
        await _commit_session(context)
    except Exception:
        logger.exception("handle_report_error")
        if update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Oops! Something unexpected happened. Please try again.",
            )
