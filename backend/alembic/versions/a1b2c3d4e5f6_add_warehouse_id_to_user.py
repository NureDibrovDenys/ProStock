"""Add warehouse_id to user table

Revision ID: a1b2c3d4e5f6
Revises: 8b1c4f2d9a10
Create Date: 2026-10-31 03:32:00.000000

Зміни:
- Додає стовпець `warehouse_id` (nullable FK → warehouse.warehouse_id) до таблиці `user`.
- При видаленні складу значення встановлюється в NULL (ON DELETE SET NULL).
- Адміністратори (root/administrator) можуть не мати прив'язки до складу — це норма.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '8b1c4f2d9a10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Додаємо стовпець warehouse_id до таблиці user
    op.add_column(
        'user',
        sa.Column(
            'warehouse_id',
            sa.BigInteger(),
            nullable=True,
        )
    )
    # Додаємо зовнішній ключ
    op.create_foreign_key(
        'fk_user_warehouse_id',
        'user',
        'warehouse',
        ['warehouse_id'],
        ['warehouse_id'],
        ondelete='SET NULL',
    )
    # Індекс для швидкої вибірки всіх співробітників складу
    op.create_index(
        'ix_user_warehouse_id',
        'user',
        ['warehouse_id'],
        unique=False,
    )
    op.execute("UPDATE \"user\" SET warehouse_id = 1 WHERE warehouse_id IS NULL")


def downgrade() -> None:
    op.drop_index('ix_user_warehouse_id', table_name='user')
    op.drop_constraint('fk_user_warehouse_id', 'user', type_='foreignkey')
    op.drop_column('user', 'warehouse_id')
