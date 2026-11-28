"""merge lpn and warehouse task revisions

Revision ID: 599682d998c7
Revises: 7b0307f675c1, 977c93526dcb
Create Date: 2026-11-27 16:56:15.953142

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '599682d998c7'
down_revision: Union[str, None] = ('7b0307f675c1', '977c93526dcb')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass