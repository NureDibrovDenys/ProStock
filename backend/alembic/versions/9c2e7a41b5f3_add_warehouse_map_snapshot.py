"""Add warehouse map snapshot

Revision ID: 9c2e7a41b5f3
Revises: 8b1c4f2d9a10
Create Date: 2026-10-26 18:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9c2e7a41b5f3'
down_revision: Union[str, None] = '8b1c4f2d9a10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'warehouse_map',
        sa.Column('warehouse_map_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('warehouse_id', sa.BigInteger(), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['warehouse_id'], ['warehouse.warehouse_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('warehouse_map_id'),
        sa.UniqueConstraint('warehouse_id'),
    )
    op.create_index(op.f('ix_warehouse_map_warehouse_id'), 'warehouse_map', ['warehouse_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_warehouse_map_warehouse_id'), table_name='warehouse_map')
    op.drop_table('warehouse_map')
