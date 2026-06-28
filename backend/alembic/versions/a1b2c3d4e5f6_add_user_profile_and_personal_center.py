"""add_user_profile_fields_and_personal_center_tables

Revision ID: a1b2c3d4e5f6
Revises: e029e83b528f
Create Date: 2026-06-28 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "e029e83b528f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add user profile columns + notifications, user_history, user_binds tables."""
    # Add new columns to users table
    op.add_column("users", sa.Column("nickname", sa.String(100), nullable=True, server_default=""))
    op.add_column("users", sa.Column("phone", sa.String(20), nullable=True, server_default=""))
    op.add_column("users", sa.Column("avatar_url", sa.String(500), nullable=True, server_default=""))

    # Create notifications table
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=True, server_default=""),
        sa.Column("category", sa.String(50), nullable=True, server_default="system"),
        sa.Column("is_read", sa.Boolean(), nullable=True, server_default=sa.text("0")),
        sa.Column("resource_type", sa.String(50), nullable=True, server_default=""),
        sa.Column("resource_id", sa.String(), nullable=True, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_user_read", "notifications", ["user_id", "is_read"])

    # Create user_history table
    op.create_table(
        "user_history",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("action_label", sa.String(200), nullable=True, server_default=""),
        sa.Column("resource_type", sa.String(50), nullable=True, server_default=""),
        sa.Column("resource_id", sa.String(), nullable=True, server_default=""),
        sa.Column("detail", sa.Text(), nullable=True, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_user_history_user_id", "user_history", ["user_id"])
    op.create_index("ix_user_history_user_action", "user_history", ["user_id", "action_type"])

    # Create user_binds table
    op.create_table(
        "user_binds",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_name", sa.String(100), nullable=True, server_default=""),
        sa.Column("provider_uid", sa.String(200), nullable=True, server_default=""),
        sa.Column("is_bound", sa.Boolean(), nullable=True, server_default=sa.text("1")),
        sa.Column("bound_at", sa.DateTime(), nullable=True),
        sa.Column("unbound_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "provider"),
    )
    op.create_index("ix_user_binds_user_id", "user_binds", ["user_id"])


def downgrade() -> None:
    """Remove personal center tables and user profile columns."""
    op.drop_table("user_binds")
    op.drop_table("user_history")
    op.drop_table("notifications")
    op.drop_column("users", "avatar_url")
    op.drop_column("users", "phone")
    op.drop_column("users", "nickname")
