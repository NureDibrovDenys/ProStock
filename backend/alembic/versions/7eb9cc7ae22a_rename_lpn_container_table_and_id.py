"""rename lpn container table and id

Revision ID: 7eb9cc7ae22a
Revises: a5c366316b96
Create Date: 2026-11-24 15:39:24.386928

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7eb9cc7ae22a'
down_revision: Union[str, None] = 'a5c366316b96'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("lpn_containter", "lpn_container")
    op.alter_column(
        "lpn_container",
        "lpn_containter_id",
        new_column_name="lpn_container_id",
    )


def downgrade() -> None:
    op.alter_column(
        "lpn_container",
        "lpn_container_id",
        new_column_name="lpn_containter_id",
    )
    op.rename_table("lpn_container", "lpn_containter")