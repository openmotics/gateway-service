"""Added screens

Revision ID: 9813cf3ca8f3
Revises: 916a8d2791e5
Create Date: 2022-06-08 13:09:18.554392

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9813cf3ca8f3'
down_revision = '916a8d2791e5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('screen',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('room_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('in_use', sa.Boolean(), nullable=False),
        sa.Column('type', sa.String(length=255), nullable=False),
        sa.Column('translational_steps', sa.Integer(), nullable=True),
        sa.Column('rotational_steps', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(length=255), nullable=False),
        sa.Column('external_id', sa.String(length=255), nullable=False),
        sa.Column('plugin_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['plugin_id'], ['plugin.id'], name=op.f('fk_screen_plugin_id_plugin'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['room_id'], ['room.id'], name=op.f('fk_screen_room_id_room'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_screen')),
        sqlite_autoincrement=True
    )


def downgrade():
    op.drop_table('screen')
