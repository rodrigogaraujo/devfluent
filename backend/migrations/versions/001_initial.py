"""initial schema

Revision ID: 001_initial
Revises:
Create Date: 2026-02-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # users
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("current_level", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column("cefr_estimate", sa.String(2), nullable=True),
        sa.Column("onboarding_done", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("subscription", sa.String(20), server_default="free", nullable=False),
        sa.Column("weekly_goal_min", sa.Integer(), server_default="60", nullable=False),
        sa.Column("timezone", sa.String(50), server_default="America/Sao_Paulo", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("tech_role", sa.String(30), nullable=True),
        sa.Column("tech_stack", JSONB(), server_default="[]", nullable=False),
        sa.Column("goals", JSONB(), server_default="[]", nullable=False),
        sa.Column("target_stack", JSONB(), server_default="[]", nullable=False),
        sa.Column("target_company", sa.String(30), server_default="startup", nullable=False),
    )

    # conversations
    op.create_table(
        "conversations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("mode", sa.String(30), nullable=False),
        sa.Column("topic", sa.String(255), nullable=True),
        sa.Column("level_at_time", sa.SmallInteger(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("errors_found", JSONB(), nullable=True),
        sa.Column("new_vocab", JSONB(), nullable=True),
    )
    op.create_index("ix_conversations_user_created", "conversations", ["user_id", "created_at"])

    # messages
    op.create_table(
        "messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("content_audio", sa.String(500), nullable=True),
        sa.Column("transcription", sa.Text(), nullable=True),
        sa.Column("corrections", JSONB(), nullable=True),
        sa.Column("pronunciation", JSONB(), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
    )
    op.create_index("ix_messages_conv_created", "messages", ["conversation_id", "created_at"])

    # assessments
    op.create_table(
        "assessments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("level_before", sa.SmallInteger(), nullable=True),
        sa.Column("level_after", sa.SmallInteger(), nullable=True),
        sa.Column("scores", JSONB(), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=True),
    )

    # study_plans
    op.create_table(
        "study_plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("level", sa.SmallInteger(), nullable=False),
        sa.Column("week_number", sa.SmallInteger(), nullable=False),
        sa.Column("theme", sa.String(255), nullable=True),
        sa.Column("focus_skills", JSONB(), nullable=True),
        sa.Column("target_vocab", JSONB(), nullable=True),
        sa.Column("completed", sa.Boolean(), server_default="false", nullable=False),
    )

    # user_vocabulary
    op.create_table(
        "user_vocabulary",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("word", sa.String(255), nullable=False),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("level_learned", sa.SmallInteger(), nullable=True),
        sa.Column("times_seen", sa.Integer(), server_default="1", nullable=False),
        sa.Column("times_used", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_review", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ease_factor", sa.Float(), server_default="2.5", nullable=False),
    )
    op.create_unique_constraint("uq_user_vocabulary_user_word", "user_vocabulary", ["user_id", "word"])
    op.create_index("ix_user_vocabulary_review", "user_vocabulary", ["user_id", "next_review"])

    # user_error_patterns
    op.create_table(
        "user_error_patterns",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("error_type", sa.String(50), nullable=True),
        sa.Column("error_detail", sa.String(255), nullable=True),
        sa.Column("correction", sa.Text(), nullable=True),
        sa.Column("occurrence_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
    )
    op.create_unique_constraint("uq_error_patterns_user_type_detail", "user_error_patterns", ["user_id", "error_type", "error_detail"])
    op.create_index("ix_error_patterns_user_count", "user_error_patterns", ["user_id", "occurrence_count"])

    # weekly_metrics
    op.create_table(
        "weekly_metrics",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("minutes_practiced", sa.Integer(), server_default="0", nullable=False),
        sa.Column("messages_sent", sa.Integer(), server_default="0", nullable=False),
        sa.Column("audio_messages", sa.Integer(), server_default="0", nullable=False),
        sa.Column("new_words", sa.Integer(), server_default="0", nullable=False),
        sa.Column("errors_grammar", sa.Integer(), server_default="0", nullable=False),
        sa.Column("errors_pronunciation", sa.Integer(), server_default="0", nullable=False),
        sa.Column("streak_days", sa.Integer(), server_default="0", nullable=False),
        sa.Column("xp_earned", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_unique_constraint("uq_weekly_metrics_user_week", "weekly_metrics", ["user_id", "week_start"])


def downgrade() -> None:
    op.drop_table("weekly_metrics")
    op.drop_table("user_error_patterns")
    op.drop_table("user_vocabulary")
    op.drop_table("study_plans")
    op.drop_table("assessments")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("users")
