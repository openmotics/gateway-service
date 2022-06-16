"""Add show_in_app field

Revision ID: 6b2a283ca697
Revises: 5349e3b38b61
Create Date: 2022-03-29 07:01:43.448810

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6b2a283ca697'
down_revision = '5349e3b38b61'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('groupaction', schema=None) as batch_op:
        batch_op.add_column(sa.Column('show_in_app', sa.Boolean(), nullable=True))
    op.execute('UPDATE "groupaction" SET show_in_app = 1')
    with op.batch_alter_table('groupaction', schema=None) as batch_op:
        batch_op.alter_column('show_in_app', nullable=False)


def downgrade():
    with op.batch_alter_table('groupaction', schema=None) as batch_op:
        batch_op.drop_column('show_in_app')
