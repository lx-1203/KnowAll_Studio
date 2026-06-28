"""enhance_knowledge_system

Revision ID: c4d5e6f7a8b9
Revises: b2c3d4e5f6a7
Create Date: 2026-06-28 20:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add knowledge summary, coverage, review queue, vocabulary tables + extend existing models."""
    # ---- New Tables ----

    # 1. knowledge_summaries
    op.create_table(
        "knowledge_summaries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content_md", sa.Text, nullable=False),
        sa.Column("node_count", sa.Integer, server_default="0"),
        sa.Column("level_stats", sa.JSON, server_default="{}"),
        sa.Column("model_used", sa.String(64)),
        sa.Column("generation_cache_key", sa.String(128), unique=True),
        sa.Column("generated_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime),
    )

    # 2. knowledge_point_nodes
    op.create_table(
        "knowledge_point_nodes",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("summary_id", sa.String(36), sa.ForeignKey("knowledge_summaries.id", ondelete="CASCADE")),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", sa.String(64)),
        sa.Column("level", sa.Integer, nullable=False),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("explanation", sa.Text, nullable=False),
        sa.Column("related_concepts", sa.Text),
        sa.Column("examples", sa.Text),
        sa.Column("tags", sa.JSON, server_default="[]"),
        sa.Column("created_at", sa.DateTime),
    )

    # 3. knowledge_coverage
    op.create_table(
        "knowledge_coverage",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("knowledge_point_id", sa.String(64), sa.ForeignKey("knowledge_point_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resource_type", sa.String(32), nullable=False),
        sa.Column("resource_id", sa.String(36), nullable=False),
        sa.Column("is_primary", sa.Boolean, server_default="1"),
        sa.Column("created_at", sa.DateTime),
        sa.UniqueConstraint("knowledge_point_id", "resource_type", "resource_id"),
    )

    # 4. review_queue
    op.create_table(
        "review_queue",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, server_default="local_user"),
        sa.Column("resource_type", sa.String(32), nullable=False),
        sa.Column("resource_id", sa.String(36), nullable=False),
        sa.Column("knowledge_point_id", sa.String(64)),
        sa.Column("priority", sa.Integer, server_default="0"),
        sa.Column("reason", sa.String(64)),
        sa.Column("pushed_at", sa.DateTime),
        sa.Column("completed", sa.Boolean, server_default="0"),
        sa.Column("completed_at", sa.DateTime),
    )

    # 5. language_vocabulary
    op.create_table(
        "language_vocabulary",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("word", sa.String(128), nullable=False),
        sa.Column("phonetic", sa.String(64)),
        sa.Column("part_of_speech", sa.String(32)),
        sa.Column("definition", sa.Text, nullable=False),
        sa.Column("example_sentence", sa.Text),
        sa.Column("difficulty", sa.String(16), server_default="medium"),
        sa.Column("knowledge_point_id", sa.String(64)),
        sa.Column("mastered", sa.Boolean, server_default="0"),
        sa.Column("created_at", sa.DateTime),
        sa.UniqueConstraint("document_id", "word"),
    )

    # ---- Extend Existing Tables ----

    # answer_records: add time_spent_ms, attempt_count, knowledge_point_ids, is_review_queue
    op.add_column("answer_records", sa.Column("time_spent_ms", sa.Integer, server_default="0"))
    op.add_column("answer_records", sa.Column("attempt_count", sa.Integer, server_default="1"))
    op.add_column("answer_records", sa.Column("knowledge_point_ids", sa.JSON, server_default="[]"))
    op.add_column("answer_records", sa.Column("is_review_queue", sa.Boolean, server_default="0"))

    # flashcards: add knowledge_point_id, review_count, correct_count, last_review_at, accuracy_rate
    op.add_column("flashcards", sa.Column("knowledge_point_id", sa.String(64)))
    op.add_column("flashcards", sa.Column("review_count", sa.Integer, server_default="0"))
    op.add_column("flashcards", sa.Column("correct_count", sa.Integer, server_default="0"))
    op.add_column("flashcards", sa.Column("last_review_at", sa.DateTime))
    op.add_column("flashcards", sa.Column("accuracy_rate", sa.Float, server_default="0.0"))

    # study_plans: add plan_type, daily_hours, knowledge_point_ids, ebbinghaus_nodes
    op.add_column("study_plans", sa.Column("plan_type", sa.String(16), server_default="long"))
    op.add_column("study_plans", sa.Column("daily_hours", sa.Float, server_default="2.0"))
    op.add_column("study_plans", sa.Column("knowledge_point_ids", sa.JSON, server_default="[]"))
    op.add_column("study_plans", sa.Column("ebbinghaus_nodes", sa.JSON, server_default="[]"))


def downgrade() -> None:
    """Revert all changes."""
    # Remove new columns from existing tables
    op.drop_column("study_plans", "ebbinghaus_nodes")
    op.drop_column("study_plans", "knowledge_point_ids")
    op.drop_column("study_plans", "daily_hours")
    op.drop_column("study_plans", "plan_type")

    op.drop_column("flashcards", "accuracy_rate")
    op.drop_column("flashcards", "last_review_at")
    op.drop_column("flashcards", "correct_count")
    op.drop_column("flashcards", "review_count")
    op.drop_column("flashcards", "knowledge_point_id")

    op.drop_column("answer_records", "is_review_queue")
    op.drop_column("answer_records", "knowledge_point_ids")
    op.drop_column("answer_records", "attempt_count")
    op.drop_column("answer_records", "time_spent_ms")

    # Drop new tables in reverse dependency order
    op.drop_table("language_vocabulary")
    op.drop_table("review_queue")
    op.drop_table("knowledge_coverage")
    op.drop_table("knowledge_point_nodes")
    op.drop_table("knowledge_summaries")
