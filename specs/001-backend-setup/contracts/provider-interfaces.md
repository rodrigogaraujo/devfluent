# Provider Interfaces Contract

**Feature**: 001-backend-setup
**Date**: 2026-02-22
**Location**: `backend/src/ai/` and `backend/src/channels/`

## Overview

All external service integrations are behind abstract interfaces (Python ABCs) per constitution principle III. Each provider defines input/output types as dataclasses, enabling independent testing via mock implementations.

---

## 1. LLMProvider (`backend/src/ai/llm.py`)

**MVP implementation**: `OpenAILLM` (GPT-4o)

```python
class LLMProvider(ABC):
    @abstractmethod
    async def chat(
        self,
        system_prompt: str,
        messages: list[dict],       # [{"role": "user"|"assistant", "content": str}]
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> LLMResponse: ...

    @abstractmethod
    async def chat_json(
        self,
        system_prompt: str,
        messages: list[dict],
        schema: dict | None = None,
    ) -> dict: ...

@dataclass
class LLMResponse:
    content: str
    input_tokens: int
    output_tokens: int
    model: str
```

**Consumers**: ConversationEngine, AssessmentEngine, MockInterviewEngine, SummaryGenerator, FeedbackAnalyzer

---

## 2. STTProvider (`backend/src/ai/stt.py`)

**MVP implementation**: `GroqSTT` (Whisper Large V3)

```python
class STTProvider(ABC):
    @abstractmethod
    async def transcribe(
        self,
        audio_bytes: bytes,
        language: str = "en",
    ) -> STTResult: ...

@dataclass
class STTResult:
    text: str
    language: str
    duration_seconds: float
```

**Consumers**: Bot handlers (voice message processing)

---

## 3. TTSProvider (`backend/src/ai/tts.py`)

**MVP implementation**: `OpenAITTS` (gpt-4o-mini-tts)

```python
class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(
        self,
        text: str,
        speed: float = 1.0,
        voice: str = "nova",
    ) -> bytes: ...  # Returns audio bytes (opus format)
```

**Consumers**: ConversationEngine (response audio generation)

**Speed by level**: 0.85 (L1), 1.0 (L2), 1.05 (L3), 1.10 (L4)

---

## 4. ContextProvider (`backend/src/ai/context.py`)

**MVP implementation**: `SQLContextProvider`
**Future**: `VectorContextProvider` (Phase 2), `RAGContextProvider` (Phase 3)

```python
class ContextProvider(ABC):
    @abstractmethod
    async def assemble(
        self,
        user_id: str,
        current_message: str,
        max_tokens: int = 4000,
    ) -> AssembledContext: ...

@dataclass
class AssembledContext:
    user_profile: str           # Layer 1: ~300 tokens (includes tech_role, tech_stack, goals, target_stack, target_company)
    conversation_history: list  # Layer 2: ~2-3K tokens
    memory_summaries: list      # Layer 3: ~500-1K tokens
    total_tokens: int

    def to_system_prompt(self, base_prompt: str) -> str:
        """Inject profile and summaries into system prompt template."""
        ...

    def to_messages(self) -> list[dict]:
        """Return conversation history formatted for OpenAI API."""
        ...
```

**Consumers**: ConversationEngine (sole consumer — critical interface per ADR-004)

---

## 5. MessageChannel (`backend/src/channels/base.py`)

**MVP implementation**: `TelegramChannel`
**Future**: `WhatsAppChannel` (Phase 2)

```python
class MessageChannel(ABC):
    @abstractmethod
    async def send_text(self, chat_id: str, text: str, **kwargs) -> None: ...

    @abstractmethod
    async def send_audio(self, chat_id: str, audio: bytes, caption: str = "", **kwargs) -> None: ...

    @abstractmethod
    async def send_keyboard(self, chat_id: str, text: str, options: list[list[str]], **kwargs) -> None: ...

    @abstractmethod
    async def download_audio(self, file_id: str) -> bytes: ...

@dataclass
class IncomingMessage:
    chat_id: str
    user_id: str
    user_name: str
    text: str | None
    audio_file_id: str | None
    is_audio: bool
    raw: Any  # Original framework object
```

**Consumers**: Bot handlers, NotificationService, ReportService

---

## 6. StorageProvider (`backend/src/utils/storage.py`)

**MVP implementation**: `R2Storage` (opt-in, Cloudflare R2 via S3-compatible API)

```python
class StorageProvider(ABC):
    @abstractmethod
    async def upload(self, key: str, data: bytes, content_type: str) -> str: ...  # Returns URL

    @abstractmethod
    async def download(self, key: str) -> bytes: ...

class NullStorage(StorageProvider):
    """No-op implementation when R2 is not configured."""
    async def upload(self, key, data, content_type): return ""
    async def download(self, key): return b""
```

**Key format**: `audio/{user_id}/{conversation_id}/{message_id}.opus`
**Consumers**: Audio pipeline (optional — system works without storage)

---

## Core Domain Interfaces

### ConversationEngine (`backend/src/core/conversation.py`)

```python
class ConversationEngine:
    def __init__(
        self,
        db: AsyncSession,
        llm: LLMProvider,
        context_provider: ContextProvider,
        tts: TTSProvider,
    ): ...

    async def process_message(
        self,
        user: User,
        text: str,
        is_audio: bool = False,
        audio_transcription: str | None = None,
    ) -> ConversationResponse: ...

    async def end_conversation(self, conversation_id: UUID) -> str: ...

@dataclass
class ConversationResponse:
    text: str
    audio_bytes: bytes | None
    corrections: list[dict] | None
    new_vocab: list[str] | None
    tokens_used: int
```

### AssessmentEngine (`backend/src/core/assessment.py`)

```python
class AssessmentEngine:
    def __init__(self, db: AsyncSession, llm: LLMProvider, channel: MessageChannel): ...

    async def start_onboarding(self, user: User) -> str:
        """Start 5-phase onboarding: creates assessment conversation, sends welcome."""
        ...

    async def process_step(self, user: User, message: str, step: str) -> AssessmentStep:
        """Process each onboarding step. Returns next question or result."""
        ...

    async def save_tech_profile(self, user: User, tech_role: str, tech_stack: list[str]) -> None:
        """Save tech_role and tech_stack to user record."""
        ...

    async def save_goals(
        self, user: User, goals: list[str],
        target_stack: list[str] | None, target_company: str | None
    ) -> None:
        """Save goals, target_stack, target_company to user record."""
        ...

    async def classify_level(self, user: User, conversation_id: UUID) -> AssessmentResult:
        """Classify user level considering tech_role and goals for personalized feedback."""
        ...

@dataclass
class AssessmentResult:
    level: int                # 1-4
    cefr: str                 # A2, B1, B2, C1
    confidence: float         # 0-1
    strengths: list[str]
    weaknesses: list[str]
    feedback: str             # Feedback text in Portuguese
    suggested_focus: str      # Based on goals: "Your HR interview prep should start with..."
```

**Onboarding state machine** (stored in Redis with 1h TTL):
```
WELCOME → SELF_DECLARATION → TECH_ROLE → TECH_STACK
→ GOALS → TARGET_STACK (conditional) → TARGET_COMPANY
→ WRITTEN_1 → WRITTEN_2 → WRITTEN_3 (optional)
→ SPEAKING → CLASSIFYING → DONE
```

### SummaryGenerator (`backend/src/core/summary.py`)

```python
class SummaryGenerator:
    def __init__(self, db: AsyncSession, llm: LLMProvider): ...

    async def generate(self, conversation_id: UUID) -> str:
        """Generate 3-4 sentence summary, extract errors/vocab, update patterns."""
        ...
```

---

## Dependency Injection Map

All providers are injected via constructor arguments (manual DI). No service container or framework-level DI required for MVP.

```
FastAPI lifespan
  └─ Creates concrete providers (OpenAILLM, GroqSTT, OpenAITTS, SQLContextProvider, TelegramChannel)
     └─ Injects into ConversationEngine, AssessmentEngine, etc.
        └─ Services call only abstract interfaces, never concrete implementations
```

**Rule**: `backend/src/core/` MUST NOT import any concrete provider class. Only ABC types.
