
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '9cf6168254d3'
down_revision: Union[str, None] = '212f6b08f028'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column(
        'inbound_order',
        sa.Column('warehouse_id', sa.BigInteger(), nullable=True),
    )
    op.add_column(
        'outbound_order',
        sa.Column('warehouse_id', sa.BigInteger(), nullable=True),
    )

    op.execute(
        "UPDATE inbound_order SET warehouse_id = "
        "(SELECT MIN(warehouse_id) FROM warehouse) WHERE warehouse_id IS NULL"
    )
    op.execute(
        "UPDATE outbound_order SET warehouse_id = "
        "(SELECT MIN(warehouse_id) FROM warehouse) WHERE warehouse_id IS NULL"
    )
    op.execute("DELETE FROM inbound_order WHERE warehouse_id IS NULL")
    op.execute("DELETE FROM outbound_order WHERE warehouse_id IS NULL")

    op.alter_column(
        'inbound_order',
        'warehouse_id',
        existing_type=sa.BigInteger(),
        nullable=False,
    )
    op.alter_column(
        'outbound_order',
        'warehouse_id',
        existing_type=sa.BigInteger(),
        nullable=False,
    )
    op.create_index(
        op.f('ix_inbound_order_warehouse_id'), 'inbound_order', ['warehouse_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_outbound_order_warehouse_id'), 'outbound_order', ['warehouse_id'],
        unique=False,
    )
    op.create_foreign_key(
        'fk_inbound_order_warehouse',
        'inbound_order',
        'warehouse',
        ['warehouse_id'],
        ['warehouse_id'],
        ondelete='RESTRICT',
    )
    op.create_foreign_key(
        'fk_outbound_order_warehouse',
        'outbound_order',
        'warehouse',
        ['warehouse_id'],
        ['warehouse_id'],
        ondelete='RESTRICT',
    )

    op.create_table(
        'stock_item',
        sa.Column('stock_item_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('product_id', sa.BigInteger(), nullable=False),
        sa.Column('shelf_id', sa.BigInteger(), nullable=False),
        sa.Column('warehouse_id', sa.BigInteger(), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column('package_type', sa.String(length=30), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.CheckConstraint('quantity > 0', name='check_stock_item_quantity_positive'),
        sa.ForeignKeyConstraint(
            ['product_id'], ['product.product_id'], ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['shelf_id'], ['shelf.shelf_id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['warehouse_id'], ['warehouse.warehouse_id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('stock_item_id'),
        sa.UniqueConstraint(
            'shelf_id',
            'product_id',
            'package_type',
            name='uq_stock_item_shelf_product_package',
        ),
    )
    op.create_index(op.f('ix_stock_item_product_id'), 'stock_item', ['product_id'], unique=False)
    op.create_index(op.f('ix_stock_item_shelf_id'), 'stock_item', ['shelf_id'], unique=False)
    op.create_index(op.f('ix_stock_item_warehouse_id'), 'stock_item', ['warehouse_id'], unique=False)

    op.create_table(
        'stock_movement',
        sa.Column('stock_movement_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('product_id', sa.BigInteger(), nullable=False),
        sa.Column('shelf_id', sa.BigInteger(), nullable=False),
        sa.Column('warehouse_id', sa.BigInteger(), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column(
            'movement_type',
            sa.Enum(
                'INBOUND_ORDER',
                'OUTBOUND_ORDER',
                'MANUAL',
                name='stock_movement_type',
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column('order_id', sa.BigInteger(), nullable=True),
        sa.Column('created_by_user_id', sa.BigInteger(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.CheckConstraint('quantity <> 0', name='check_stock_movement_quantity_not_zero'),
        sa.ForeignKeyConstraint(
            ['product_id'], ['product.product_id'], ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['shelf_id'], ['shelf.shelf_id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['warehouse_id'], ['warehouse.warehouse_id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['created_by_user_id'], ['user.user_id'], ondelete='RESTRICT'
        ),
        sa.PrimaryKeyConstraint('stock_movement_id'),
    )
    op.create_index(op.f('ix_stock_movement_product_id'), 'stock_movement', ['product_id'], unique=False)
    op.create_index(op.f('ix_stock_movement_shelf_id'), 'stock_movement', ['shelf_id'], unique=False)
    op.create_index(op.f('ix_stock_movement_warehouse_id'), 'stock_movement', ['warehouse_id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_stock_movement_warehouse_id'), table_name='stock_movement')
    op.drop_index(op.f('ix_stock_movement_shelf_id'), table_name='stock_movement')
    op.drop_index(op.f('ix_stock_movement_product_id'), table_name='stock_movement')
    op.drop_table('stock_movement')

    op.drop_index(op.f('ix_stock_item_warehouse_id'), table_name='stock_item')
    op.drop_index(op.f('ix_stock_item_shelf_id'), table_name='stock_item')
    op.drop_index(op.f('ix_stock_item_product_id'), table_name='stock_item')
    op.drop_table('stock_item')

    op.drop_constraint('fk_outbound_order_warehouse', 'outbound_order', type_='foreignkey')
    op.drop_index(op.f('ix_outbound_order_warehouse_id'), table_name='outbound_order')
    op.drop_column('outbound_order', 'warehouse_id')

    op.drop_constraint('fk_inbound_order_warehouse', 'inbound_order', type_='foreignkey')
    op.drop_index(op.f('ix_inbound_order_warehouse_id'), table_name='inbound_order')
    op.drop_column('inbound_order', 'warehouse_id')
