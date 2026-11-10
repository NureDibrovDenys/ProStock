"""Create recipient table

Revision ID: e7f8a9b0c1d2
Revises: d4e5f6a7b8c9
Create Date: 2026-11-10 13:08:00

Додає таблицю recipient — довідник одержувачів товару для вихідних накладних.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'recipient',
        sa.Column('recipient_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('company_name', sa.String(length=255), nullable=False),
        sa.Column('tax_id', sa.String(length=20), nullable=True),
        sa.Column('contact_person', sa.String(length=150), nullable=True),
        sa.Column('phone_number', sa.String(length=30), nullable=True),
        sa.Column('recipient_email', sa.String(length=100), nullable=True),
        sa.Column('delivery_address', sa.Text(), nullable=False),
        sa.Column(
            'recipient_status',
            sa.Enum('ACTIVE', 'INACTIVE', 'BLOCKED', name='recipient_status', native_enum=False),
            server_default='ACTIVE',
            nullable=False,
        ),
        sa.Column(
            'recipient_created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('recipient_id'),
    )


def downgrade() -> None:
    op.drop_table('recipient')