"""link lpn containers to inbound order items

Revision ID: 7b0307f675c1
Revises: 7eb9cc7ae22a
Create Date: 2026-11-27 15:31:24.495001

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7b0307f675c1'
down_revision: Union[str, None] = '7eb9cc7ae22a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "lpn_container",
        sa.Column("inbound_order_item_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "lpn_container",
        sa.Column("quantity", sa.Numeric(precision=10, scale=2), nullable=True),
    )

  
    op.create_index(
        "ix_lpn_container_inbound_order_item_id",
        "lpn_container",
        ["inbound_order_item_id"],
    )
    op.create_foreign_key(
        "lpn_container_inbound_order_item_id_fkey",
        "lpn_container",
        "inbound_order_item",
        ["inbound_order_item_id"],
        ["inbound_order_item_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "lpn_container_inbound_order_item_id_fkey",
        "lpn_container",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_lpn_container_inbound_order_item_id",
        table_name="lpn_container",
    )

  

    op.drop_column("lpn_container", "quantity")
    op.drop_column("lpn_container", "inbound_order_item_id")