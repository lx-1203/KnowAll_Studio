"""Add gamification: streaks, achievements, focus sessions

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-06-30
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'f8a9b0c1d2e3'
down_revision: Union[str, None] = 'e7f8a9b0c1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'learning_streaks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('streak_date', sa.Date(), nullable=False),
        sa.Column('study_minutes', sa.Integer(), server_default='0'),
        sa.Column('questions_answered', sa.Integer(), server_default='0'),
        sa.Column('cards_reviewed', sa.Integer(), server_default='0'),
        sa.Column('documents_uploaded', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'achievements',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('achievement_key', sa.String(64), nullable=False),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('description', sa.String(256), server_default=''),
        sa.Column('icon', sa.String(32), server_default='🏆'),
        sa.Column('unlocked_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'focus_sessions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('duration_minutes', sa.Integer(), nullable=False),
        sa.Column('session_type', sa.String(32), server_default='study'),
        sa.Column('completed', sa.Boolean(), server_default='1'),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('focus_sessions')
    op.drop_table('achievements')
    op.drop_table('learning_streaks')
