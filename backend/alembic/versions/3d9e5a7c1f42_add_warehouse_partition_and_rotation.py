"""Add warehouse_partition table and rotation_angle for obstacles and zones

Revision ID: 3d9e5a7c1f42
Revises: 8b1c4f2d9a10
Create Date: 2026-10-26 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3d9e5a7c1f42'
down_revision: Union[str, None] = '8b1c4f2d9a10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'warehouse_partition',
        sa.Column('partition_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('warehouse_id', sa.BigInteger(), nullable=False),
        sa.Column('start_x', sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column('start_y', sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column('end_x', sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column('end_y', sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column('thickness', sa.Numeric(precision=5, scale=2), server_default=sa.text('0.20'), nullable=False),
        sa.Column('height', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.CheckConstraint('thickness > 0', name='check_partition_thickness_min'),
        sa.CheckConstraint('height IS NULL OR height > 0', name='check_partition_height'),
        sa.ForeignKeyConstraint(['warehouse_id'], ['warehouse.warehouse_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('partition_id'),
    )
    op.create_index(
        op.f('ix_warehouse_partition_warehouse_id'), 'warehouse_partition', ['warehouse_id'], unique=False
    )

    for table in ('warehouse_obstacle', 'zone'):
        op.add_column(
            table,
            sa.Column('rotation_angle', sa.Numeric(precision=5, scale=2), server_default=sa.text('0.00'), nullable=False),
        )
    op.create_check_constraint(
        'check_obstacle_rotation_angle', 'warehouse_obstacle', 'rotation_angle >= 0 AND rotation_angle < 360'
    )
    op.create_check_constraint(
        'check_zone_rotation_angle', 'zone', 'rotation_angle >= 0 AND rotation_angle < 360'
    )


def downgrade() -> None:
    op.drop_constraint('check_zone_rotation_angle', 'zone', type_='check')
    op.drop_constraint('check_obstacle_rotation_angle', 'warehouse_obstacle', type_='check')
    op.drop_column('zone', 'rotation_angle')
    op.drop_column('warehouse_obstacle', 'rotation_angle')
    op.drop_index(op.f('ix_warehouse_partition_warehouse_id'), table_name='warehouse_partition')
    op.drop_table('warehouse_partition')
