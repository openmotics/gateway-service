"""Remove GroupAction in_use

Revision ID: 90221408c7a3
Revises: 1f7097fd79e4
Create Date: 2022-04-15 09:10:44.618829

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '90221408c7a3'
down_revision = '1f7097fd79e4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('groupaction', schema=None) as batch_op:
        batch_op.drop_column('in_use')


def downgrade():
    with op.batch_alter_table('groupaction', schema=None) as batch_op:
        batch_op.add_column(sa.Column('in_use', sa.Boolean(), nullable=True))
    op.execute('UPDATE "groupaction" SET in_use = 1')
    with op.batch_alter_table('groupaction', schema=None) as batch_op:
        batch_op.alter_column('in_use', nullable=False)
