"""Add in_use

Revision ID: 1f7097fd79e4
Revises: c2e6b03b000c
Create Date: 2022-04-12 10:17:56.388326

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1f7097fd79e4'
down_revision = 'c2e6b03b000c'
branch_labels = None
depends_on = None


def upgrade():
    for table in ['input', 'output', 'pulsecounter', 'sensor', 'shutter', 'shuttergroup']:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column('in_use', sa.Boolean(), nullable=True))
        op.execute('UPDATE "{0}" SET in_use = 1'.format(table))
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column('in_use', nullable=False)


def downgrade():
    for table in ['input', 'output', 'pulsecounter', 'sensor', 'shutter', 'shuttergroup']:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column('in_use')
