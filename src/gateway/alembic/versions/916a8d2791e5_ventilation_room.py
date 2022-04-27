"""ventilation_room

Revision ID: 916a8d2791e5
Revises: c2e6b03b000c
Create Date: 2022-04-13 16:48:20.798256

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '916a8d2791e5'
down_revision = '1f7097fd79e4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('ventilation', schema=None) as batch_op:
        batch_op.add_column(sa.Column('room_id', sa.Integer(), nullable=True))
        batch_op.alter_column('device_vendor',
               existing_type=sa.VARCHAR(length=255),
               nullable=True)
        batch_op.alter_column('device_type',
               existing_type=sa.VARCHAR(length=255),
               nullable=True)
        batch_op.alter_column('device_serial',
               existing_type=sa.VARCHAR(length=255),
               nullable=True)
        batch_op.create_foreign_key(batch_op.f('fk_ventilation_room_id_room'), 'room', ['room_id'], ['id'], ondelete='SET NULL')


def downgrade():
    with op.batch_alter_table('ventilation', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_ventilation_room_id_room'), type_='foreignkey')
        batch_op.alter_column('device_serial',
               existing_type=sa.VARCHAR(length=255),
               nullable=False)
        batch_op.alter_column('device_type',
               existing_type=sa.VARCHAR(length=255),
               nullable=False)
        batch_op.alter_column('device_vendor',
               existing_type=sa.VARCHAR(length=255),
               nullable=False)
        batch_op.drop_column('room_id')
