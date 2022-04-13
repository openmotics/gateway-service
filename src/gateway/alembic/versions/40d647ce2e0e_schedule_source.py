"""schedule_source

Revision ID: 40d647ce2e0e
Revises: 6b2a283ca697
Create Date: 2022-04-08 14:53:06.362772

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '40d647ce2e0e'
down_revision = '6b2a283ca697'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('schedule', schema=None) as batch_op:
        batch_op.drop_constraint('uq_schedule_source', type_='unique')
        batch_op.drop_column('external_id')
        batch_op.drop_column('source')


def downgrade():
    with op.batch_alter_table('schedule', schema=None) as batch_op:
        batch_op.add_column(sa.Column('source', sa.VARCHAR(length=255), nullable=False))
        batch_op.add_column(sa.Column('external_id', sa.VARCHAR(length=255), nullable=True))
        batch_op.create_unique_constraint('uq_schedule_source', ['source', 'external_id'])
