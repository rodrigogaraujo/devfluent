# API Contract: Webhook & Health Endpoints

**Feature**: 001-backend-setup
**Date**: 2026-02-22
**Base URL**: `https://<railway-domain>` (production) or `http://localhost:18001` (dev)

## Endpoints

### GET /health

Health check endpoint for Railway and monitoring.

**Request**: No body, no auth.

**Response 200**:
```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

**Response 503** (database unreachable):
```json
{
  "status": "degraded",
  "error": "database_unavailable"
}
```

---

### POST /webhook/telegram

Receives Telegram webhook updates. Called by Telegram servers.

**Request Headers**:
- `Content-Type: application/json`

**Request Body**: Telegram Update object (validated by PTB internally).

```json
{
  "update_id": 123456789,
  "message": {
    "message_id": 1,
    "from": {
      "id": 987654321,
      "first_name": "João",
      "language_code": "pt-br"
    },
    "chat": {
      "id": 987654321,
      "type": "private"
    },
    "date": 1708617600,
    "text": "/start"
  }
}
```

**Response 200**: Empty body (Telegram expects 200 to acknowledge receipt).

**Error handling**: All errors are caught internally. The endpoint always returns 200 to prevent Telegram from retrying. Errors are logged to Sentry and the user receives a friendly error message via Telegram.

---

## Telegram Bot Commands

| Command | Handler | Activation Required | Description |
|---------|---------|-------------------|-------------|
| `/start` | `handle_start` | No | Welcome + create user (is_active=FALSE) |
| `/level` | `handle_level` | Yes | Show current level and progress |
| `/plan` | `handle_plan` | Yes | Show weekly study plan |
| `/interview` | `handle_interview` | Yes | Start mock interview (auto-suggests based on goals) |
| `/goals` | `handle_goals` | Yes | View/edit learning goals and target stack |
| `/report` | `handle_report` | Yes | Show weekly report |
| `/help` | `handle_help` | No | List available commands |
| `/end` | `handle_end` | Yes | End current conversation + generate summary |
| `/activate <tid>` | `handle_activate` | Admin only | Activate user by telegram_id |
| `/deactivate <tid>` | `handle_deactivate` | Admin only | Deactivate user by telegram_id |
| `/users` | `handle_users` | Admin only | List all users with status |
| `/stats` | `handle_stats` | Admin only | Show usage metrics and cost estimate |

---

## Message Types Handled

| Type | Handler | Processing |
|------|---------|------------|
| Text message | `handle_text` | → ConversationEngine.process_message() |
| Voice message | `handle_voice` | → STT → ConversationEngine.process_message() |
| Callback query | `handle_callback` | → Route by callback_data (onboarding steps, keyboard responses, goal editing) |
| Unsupported (sticker, location, etc.) | `handle_unsupported` | → Reply with "I only support text and voice messages" |

---

## Middleware Pipeline

Every incoming update passes through middleware in order:

```
Update → User Lookup → Active Check → Rate Limit → Handler
```

1. **User Lookup**: Find or create user by `telegram_id`. Attach to context.
2. **Active Check**: If `is_active=FALSE` and command is not `/start` or `/help`, respond with waitlist message.
3. **Rate Limit**: Check Redis `msg_count:{user_id}:{date}` < 100. If exceeded, respond with rate limit message.

---

## Error Responses (via Telegram message)

| Scenario | User Message |
|----------|-------------|
| AI service timeout | "I'm having trouble thinking right now. Try again in a moment!" |
| STT transcription failure | "I couldn't understand that audio. Could you try again or type your message?" |
| Unsupported message type | "I only support text and voice messages for now. Try sending me a text or voice message!" |
| Rate limit exceeded | "You've been practicing a lot today! Let's continue tomorrow." |
| Non-activated user | "You're on the waitlist! We'll activate you soon." |
| Database unreachable | "Something went wrong on our end. Please try again in a few minutes." |
| Generic error | "Oops! Something unexpected happened. Please try again." |
