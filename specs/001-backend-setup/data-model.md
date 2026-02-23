# Data Model: Backend Project Setup

**Feature**: 001-backend-setup
**Date**: 2026-02-22
**Source**: PROJECT_SPEC_V3.md §5, spec.md Key Entities (updated with Tech Profile + Goal Setting)

## Entity Relationship Diagram

```
┌──────────────┐     1:N     ┌──────────────────┐     1:N     ┌──────────────┐
│    users     │────────────→│  conversations   │────────────→│   messages   │
│              │             │                  │             │              │
│ telegram_id  │             │ mode             │             │ role         │
│ current_level│             │ topic            │             │ content_text │
│ is_active    │             │ summary ★        │             │ content_audio│
│ tech_role    │             │ errors_found ★   │             │ transcription│
│ goals (JSONB)│             │ new_vocab ★      │             │ corrections  │
│ target_stack │             │                  │             │              │
└──────┬───────┘             └────────┬─────────┘             └──────────────┘
       │                              │
       │ 1:N                          │ 1:1 (optional)
       ▼                              ▼
┌──────────────────┐          ┌──────────────────┐
│ user_error_      │          │   assessments    │
│ patterns         │          │                  │
│                  │          │ type             │
│ error_type       │          │ level_before     │
│ error_detail     │          │ level_after      │
│ correction       │          │ scores (JSONB)   │
│ occurrence_count │          │ feedback         │
└──────────────────┘          └──────────────────┘

       │ 1:N                         │ 1:N
       ▼                              ▼
┌──────────────────┐          ┌──────────────────┐
│ user_vocabulary  │          │   study_plans    │
│                  │          │                  │
│ word             │          │ level            │
│ context          │          │ week_number      │
│ times_seen/used  │          │ theme            │
│ next_review      │          │ focus_skills     │
│ ease_factor      │          │ target_vocab     │
└──────────────────┘          └──────────────────┘

┌──────────────────┐
│ weekly_metrics   │
│                  │
│ week_start       │
│ minutes_practiced│
│ messages_sent    │
│ streak_days      │
│ xp_earned        │
└──────────────────┘
```

## Entities

### 1. users

Primary entity representing a developer using the platform.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, DEFAULT gen_random_uuid() | Internal identifier |
| telegram_id | BIGINT | UNIQUE NOT NULL | Telegram user ID (external identity) |
| name | VARCHAR(255) | | Display name from Telegram |
| email | VARCHAR(255) | | Optional email for future billing |
| current_level | SMALLINT | NOT NULL DEFAULT 1 | Level 1-4 |
| cefr_estimate | VARCHAR(2) | | A2, B1, B2, C1 |
| onboarding_done | BOOLEAN | DEFAULT FALSE | Has completed initial assessment |
| subscription | VARCHAR(20) | DEFAULT 'free' | free, active, inactive, cancelled |
| weekly_goal_min | INTEGER | DEFAULT 60 | Weekly practice goal in minutes |
| timezone | VARCHAR(50) | DEFAULT 'America/Sao_Paulo' | User timezone for notifications |
| is_active | BOOLEAN | DEFAULT FALSE | Activation gate for tutoring features |
| tech_role | VARCHAR(30) | | backend, frontend, fullstack, mobile, data, devops |
| tech_stack | JSONB | DEFAULT '[]' | Technologies user works with: ["python", "node", "react"] |
| goals | JSONB | DEFAULT '[]' | Learning goals: ["hr_interview", "technical_interview", "meetings", "leading"] |
| target_stack | JSONB | DEFAULT '[]' | Target job stack: ["node", "aws", "system_design"] |
| target_company | VARCHAR(30) | DEFAULT 'startup' | big_tech, startup, enterprise |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Record creation time |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | Last update time |

**Indexes**: `users.telegram_id` (UNIQUE index, implicit)
**Validation rules**:
- `current_level` must be 1-4
- `subscription` must be one of: free, active, inactive, cancelled
- `telegram_id` is immutable after creation
- `is_active` defaults to FALSE — manual admin activation required
- `tech_role` must be one of: backend, frontend, fullstack, mobile, data, devops (or NULL before onboarding)
- `goals` JSONB array entries must be from: hr_interview, technical_interview, meetings, leading
- `target_company` must be one of: big_tech, startup, enterprise

**State transitions**:
- New user → `is_active=FALSE, onboarding_done=FALSE, subscription='free'`
- Tech profile collected → `tech_role` and `tech_stack` populated
- Goals collected → `goals`, `target_stack` (conditional), `target_company` populated
- Admin activates → `is_active=TRUE, subscription='active'`
- Completes onboarding → `onboarding_done=TRUE, current_level=<assessed>`
- Updates goals via `/goals` → `goals`, `target_stack`, `target_company` updated, study plan regenerated
- Level check → `current_level` can only increase (never decrease)
- Admin deactivates → `is_active=FALSE, subscription='inactive'`

### 2. conversations

A session of interaction between user and AI tutor.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| user_id | UUID | FK → users(id) | |
| mode | VARCHAR(30) | NOT NULL | free_chat, mock_interview, assessment, lesson |
| topic | VARCHAR(255) | | Conversation topic (detected or set) |
| level_at_time | SMALLINT | | User level when conversation started |
| started_at | TIMESTAMPTZ | DEFAULT NOW() | |
| ended_at | TIMESTAMPTZ | | NULL while active, set on end |
| summary | TEXT | | Generated by LLM at session end |
| errors_found | JSONB | | Structured errors extracted from session |
| new_vocab | JSONB | | New vocabulary learned in session |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | |

**Indexes**:
- `conversations(user_id, created_at DESC)` — fetch latest conversations
- `conversations(user_id) WHERE summary IS NOT NULL` — partial index for memory summaries

**Validation rules**:
- `mode` must be one of: free_chat, mock_interview, assessment, lesson
- `ended_at` must be >= `started_at` when set
- `summary` is NULL until conversation ends

**State transitions**:
- Created → `ended_at=NULL, summary=NULL`
- Ended (timeout or /end) → `ended_at=NOW()`, summary generated
- Auto-create: if user sends message with no active conversation (no `ended_at=NULL` row, or last message >30min ago), create new conversation silently

### 3. messages

Individual messages within a conversation.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| conversation_id | UUID | FK → conversations(id) | |
| role | VARCHAR(10) | NOT NULL | 'user' or 'assistant' |
| content_text | TEXT | | Text content |
| content_audio | VARCHAR(500) | | URL to audio file in R2 (optional) |
| transcription | TEXT | | STT transcription of voice message |
| corrections | JSONB | | Inline corrections made by tutor |
| pronunciation | JSONB | | Pronunciation feedback |
| tokens_used | INTEGER | | Tokens consumed by this interaction |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | |

**Indexes**:
- `messages(conversation_id, created_at)` — fetch messages in order
- `messages(conversation_id, created_at DESC)` — fetch latest N messages

**Validation rules**:
- `role` must be 'user' or 'assistant'
- Either `content_text` or `transcription` must be non-null (message must have text content)
- `content_audio` is optional (only for voice messages and TTS responses)

### 4. assessments

Periodic evaluations of user level.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| user_id | UUID | FK → users(id) | |
| type | VARCHAR(20) | NOT NULL | onboarding, level_check, mock_interview |
| level_before | SMALLINT | | Level before assessment |
| level_after | SMALLINT | | Level after assessment |
| scores | JSONB | | { grammar, vocabulary, pronunciation, fluency } |
| feedback | TEXT | | Human-readable feedback |
| conversation_id | UUID | FK → conversations(id) | Assessment conversation |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | |

**Validation rules**:
- `type` must be one of: onboarding, level_check, mock_interview
- `level_after >= level_before` (levels never decrease)
- `scores` JSONB contains numeric values 1-10 per category

### 5. study_plans

Weekly study plans generated per user level.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| user_id | UUID | FK → users(id) | |
| level | SMALLINT | NOT NULL | Level this plan is for (1-4) |
| week_number | SMALLINT | NOT NULL | Week within level (1-12) |
| theme | VARCHAR(255) | | Weekly theme |
| focus_skills | JSONB | | Skills to practice |
| target_vocab | JSONB | | Target vocabulary words |
| completed | BOOLEAN | DEFAULT FALSE | All activities done |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | |

**Validation rules**:
- `level` must be 1-4
- `week_number` must be 1-12
- One active plan per user at a time

### 6. user_vocabulary

Individual words learned with spaced repetition metadata.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| user_id | UUID | FK → users(id) | |
| word | VARCHAR(255) | NOT NULL | The English word |
| context | TEXT | | Sentence where word was introduced |
| level_learned | SMALLINT | | User level when word was learned |
| times_seen | INTEGER | DEFAULT 1 | How many times word appeared |
| times_used | INTEGER | DEFAULT 0 | How many times user used it correctly |
| next_review | TIMESTAMPTZ | | Next spaced repetition review date |
| ease_factor | FLOAT | DEFAULT 2.5 | SM-2 ease factor |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | |

**Constraints**: `UNIQUE(user_id, word)`
**Indexes**: `user_vocabulary(user_id, next_review)` — spaced repetition queries

**Spaced repetition (SM-2 simplified)**:
```
intervals = [1, 3, 7, 14, 30, 60] days
next_review = now() + intervals[min(times_used, 5)] * ease_factor
```

### 7. user_error_patterns

Aggregated recurring errors per user.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| user_id | UUID | FK → users(id) | |
| error_type | VARCHAR(50) | | grammar, pronunciation, vocabulary |
| error_detail | VARCHAR(255) | | Specific error (e.g., "present_perfect", "th_sound") |
| correction | TEXT | | Example correction |
| occurrence_count | INTEGER | DEFAULT 1 | Times this error occurred |
| last_seen | TIMESTAMPTZ | DEFAULT NOW() | Most recent occurrence |

**Constraints**: `UNIQUE(user_id, error_type, error_detail)`
**Indexes**: `user_error_patterns(user_id, occurrence_count DESC)` — top errors for context

**Update pattern**: UPSERT — if error already exists for user, increment `occurrence_count` and update `last_seen` and `correction`.

### 8. weekly_metrics

Aggregated usage statistics per user per week.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| user_id | UUID | FK → users(id) | |
| week_start | DATE | NOT NULL | Monday of the week |
| minutes_practiced | INTEGER | DEFAULT 0 | Total practice time |
| messages_sent | INTEGER | DEFAULT 0 | Text + voice messages |
| audio_messages | INTEGER | DEFAULT 0 | Voice messages only |
| new_words | INTEGER | DEFAULT 0 | Words learned this week |
| errors_grammar | INTEGER | DEFAULT 0 | Grammar errors detected |
| errors_pronunciation | INTEGER | DEFAULT 0 | Pronunciation errors detected |
| streak_days | INTEGER | DEFAULT 0 | Consecutive practice days |
| xp_earned | INTEGER | DEFAULT 0 | Experience points |

**Constraints**: `UNIQUE(user_id, week_start)`
**Indexes**: `weekly_metrics(user_id, week_start)` — implicit from UNIQUE

**Update pattern**: UPSERT — increment counters on each interaction. `week_start` is always the Monday of the current week.

## JSONB Field Schemas

### conversations.errors_found
```json
[
  {
    "type": "grammar",
    "detail": "present_perfect",
    "user_said": "I have work on this project",
    "correction": "I have worked on this project",
    "severity": "medium"
  }
]
```

### conversations.new_vocab
```json
[
  {
    "word": "trade-off",
    "context": "Every architecture has trade-offs",
    "definition": "A balance between two desirable things"
  }
]
```

### assessments.scores
```json
{
  "grammar": 7,
  "vocabulary": 6,
  "pronunciation": 5,
  "fluency": 6,
  "overall": 6
}
```

### study_plans.focus_skills
```json
["present simple", "tech vocabulary basics", "self introduction"]
```

### study_plans.target_vocab
```json
["deploy", "repository", "branch", "merge", "pull request"]
```

### messages.corrections
```json
[
  {
    "original": "I have work",
    "corrected": "I have worked",
    "explanation": "Use past participle after 'have' (present perfect)"
  }
]
```

### messages.pronunciation
```json
{
  "issues": ["th_sound", "word_stress"],
  "score": 7,
  "feedback": "Good clarity, but watch the 'th' sound in 'three'"
}
```
