"""add_bloom_and_quality_to_question_bank

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-06-28 22:00:00.000000

Add Bloom's Taxonomy cognitive_level, continuous difficulty_score,
and LLM-as-Judge review_scores/review_total to question_bank table.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, Sequence[str], None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add cognitive_level, difficulty_score, and review quality columns."""
    op.add_column("question_bank", sa.Column("difficulty_score", sa.Float, server_default="0.5"))
    op.add_column("question_bank", sa.Column("cognitive_level", sa.String(20), server_default="L2_understand"))
    op.add_column("question_bank", sa.Column("review_scores", sa.JSON, server_default="{}"))
    op.add_column("question_bank", sa.Column("review_total", sa.Float))


def downgrade() -> None:
    """Remove the added columns."""
    op.drop_column("question_bank", "review_total")
    op.drop_column("question_bank", "review_scores")
    op.drop_column("question_bank", "cognitive_level")
    op.drop_column("question_bank", "difficulty_score")
