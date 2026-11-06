"""Fix enum status case (active -> ACTIVE)

SQLAlchemy Enum(native_enum=False) зберігає ІМЕНА членів enum (ACTIVE),
а не їхні значення (active). Попередні міграції задавали server_default
у нижньому регістрі, через що в БД з'явилися рядки 'active'.

Revision ID: d4e5f6a7b8c9
Revises: 918d39ecb276
Create Date: 2026-11-06 15:30:00

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = '918d39ecb276'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (таблиця, колонка)
COLUMNS = [
    ('user', 'user_status'),
    ('shelf', 'shelf_status'),
    ('supplier', 'supplier_status'),
]


def upgrade() -> None:
    for table, column in COLUMNS:
        op.execute(f'UPDATE "{table}" SET {column} = UPPER({column}) WHERE {column} <> UPPER({column})')
        op.execute(f'ALTER TABLE "{table}" ALTER COLUMN {column} SET DEFAULT \'ACTIVE\'')


def downgrade() -> None:
    for table, column in COLUMNS:
        op.execute(f'ALTER TABLE "{table}" ALTER COLUMN {column} SET DEFAULT \'active\'')
