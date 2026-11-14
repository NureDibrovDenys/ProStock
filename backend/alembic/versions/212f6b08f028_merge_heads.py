"""merge heads

Revision ID: 212f6b08f028
Revises: 853cc6d84a38, d9e91acf1948
Create Date: 2026-11-14 21:43:07.624394

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '212f6b08f028'
down_revision: Union[str, None] = ('853cc6d84a38', 'd9e91acf1948')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass