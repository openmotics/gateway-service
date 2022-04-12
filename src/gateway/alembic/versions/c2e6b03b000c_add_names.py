"""Add names

Revision ID: c2e6b03b000c
Revises: 40d647ce2e0e
Create Date: 2022-04-11 11:11:16.298075

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c2e6b03b000c'
down_revision = '40d647ce2e0e'
branch_labels = None
depends_on = None


def upgrade():
    for table in ['groupaction', 'input', 'output', 'shutter']:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column('name', sa.String(length=255), nullable=True))
        op.execute('UPDATE "{0}" SET name = ""'.format(table))
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column('name', nullable=False)


def downgrade():
    for table in ['groupaction', 'input', 'output', 'shutter']:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column('name')
