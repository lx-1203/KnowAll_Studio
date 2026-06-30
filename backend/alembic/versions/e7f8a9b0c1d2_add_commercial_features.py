"""Add commercial features: subscriptions, licenses, payments, system config, email verification

Revision ID: e7f8a9b0c1d2
Revises: d5e6f7a8b9c0
Create Date: 2026-06-30
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # User table: add email verification fields
    op.add_column('users', sa.Column('email_verified', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('verification_token', sa.String(64), nullable=True))

    # User tiers
    op.create_table(
        'user_tiers',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('tier', sa.String(20), nullable=False, server_default='free'),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('auto_renew', sa.Boolean(), server_default='0'),
        sa.Column('daily_ai_calls_limit', sa.Integer(), server_default='50'),
        sa.Column('daily_token_limit', sa.Integer(), server_default='500000'),
        sa.Column('max_documents', sa.Integer(), server_default='10'),
        sa.Column('max_file_size_mb', sa.Integer(), server_default='20'),
        sa.Column('features_extra', sa.String(500), server_default=''),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # Licenses
    op.create_table(
        'licenses',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('license_key', sa.String(64), unique=True, nullable=False, index=True),
        sa.Column('tier', sa.String(20), nullable=False, server_default='pro'),
        sa.Column('activations_max', sa.Integer(), server_default='1'),
        sa.Column('activations_used', sa.Integer(), server_default='0'),
        sa.Column('is_active', sa.Boolean(), server_default='1'),
        sa.Column('issued_to', sa.String(200), server_default=''),
        sa.Column('issued_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
    )

    # License activations
    op.create_table(
        'license_activations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('license_id', sa.String(36), sa.ForeignKey('licenses.id'), nullable=False),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('device_id', sa.String(128), server_default=''),
        sa.Column('activated_at', sa.DateTime(), nullable=True),
    )

    # Payment orders
    op.create_table(
        'payment_orders',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('order_no', sa.String(32), unique=True, nullable=False, index=True),
        sa.Column('tier', sa.String(20), nullable=False),
        sa.Column('amount_cents', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(3), server_default='CNY'),
        sa.Column('status', sa.String(20), server_default='pending'),
        sa.Column('payment_method', sa.String(20), server_default=''),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # System config
    op.create_table(
        'system_config',
        sa.Column('key', sa.String(128), primary_key=True),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('description', sa.String(256), server_default=''),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('system_config')
    op.drop_table('payment_orders')
    op.drop_table('license_activations')
    op.drop_table('licenses')
    op.drop_table('user_tiers')
    op.drop_column('users', 'verification_token')
    op.drop_column('users', 'email_verified')
