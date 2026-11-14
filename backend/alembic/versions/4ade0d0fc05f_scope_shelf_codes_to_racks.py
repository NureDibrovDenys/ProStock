"""scope shelf codes to racks

Revision ID: 4ade0d0fc05f
Revises: 314af5682e78
Create Date: 2026-11-14 17:12:30.547400

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4ade0d0fc05f'
down_revision: Union[str, None] = '314af5682e78'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    op.drop_constraint(
        "shelf_shelf_code_key",
        "shelf",
        type_="unique",
    )

    op.create_unique_constraint(
        "uq_shelf_rack_code",
        "shelf",
        ["rack_id", "shelf_code"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_shelf_rack_code",
        "shelf",
        type_="unique",
    )

    op.create_unique_constraint(
        "shelf_shelf_code_key",
        "shelf",
        ["shelf_code"],
    )
