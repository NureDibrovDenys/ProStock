"""add units per package to product

Revision ID: 16291b715789
Revises: 599682d998c7
Create Date: 2026-11-27 17:15:17.238793

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '16291b715789'
down_revision: Union[str, None] = '599682d998c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "product",
        sa.Column("units_per_package", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "check_product_units_per_package_positive",
        "product",
        "units_per_package > 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "check_product_units_per_package_positive",
        "product",
        type_="check",
    )
    op.drop_column("product", "units_per_package")