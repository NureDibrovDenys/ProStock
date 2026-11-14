"""Create outbound orders

Revision ID: 5a6b7c8d9e0f
Revises: 314af5682e78
Create Date: 2026-11-13 11:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5a6b7c8d9e0f'
down_revision: Union[str, None] = '314af5682e78'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'outbound_order',
        sa.Column('outbound_order_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('recipient_id', sa.BigInteger(), nullable=False),
        sa.Column('invoice_number', sa.String(length=50), nullable=False),
        sa.Column('planned_shipment_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            'order_status',
            sa.Enum('DRAFT', 'IN_PROGRESS', 'READY', 'COMPLETED', 'CANCELED', name='order_status', native_enum=False),
            nullable=False,
        ),
        sa.Column('created_by_user_id', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['user.user_id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['recipient_id'], ['recipient.recipient_id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('outbound_order_id'),
        sa.UniqueConstraint('invoice_number'),
    )
    op.create_index(op.f('ix_outbound_order_recipient_id'), 'outbound_order', ['recipient_id'], unique=False)

    op.create_table(
        'outbound_order_item',
        sa.Column('outbound_order_item_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('outbound_order_id', sa.BigInteger(), nullable=False),
        sa.Column('product_id', sa.BigInteger(), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('package_type', sa.String(length=30), nullable=False),
        sa.CheckConstraint('quantity > 0', name='check_outbound_order_item_quantity_positive'),
        sa.ForeignKeyConstraint(['outbound_order_id'], ['outbound_order.outbound_order_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['product.product_id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('outbound_order_item_id'),
    )
    op.create_index(op.f('ix_outbound_order_item_outbound_order_id'), 'outbound_order_item', ['outbound_order_id'], unique=False)
    op.create_index(op.f('ix_outbound_order_item_product_id'), 'outbound_order_item', ['product_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_outbound_order_item_product_id'), table_name='outbound_order_item')
    op.drop_index(op.f('ix_outbound_order_item_outbound_order_id'), table_name='outbound_order_item')
    op.drop_table('outbound_order_item')
    op.drop_index(op.f('ix_outbound_order_recipient_id'), table_name='outbound_order')
    op.drop_table('outbound_order')