"""valve_driver

Revision ID: 0f6ba3c709b6
Revises: dd7b74eca352
Create Date: 2022-08-23 16:33:18.326993

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0f6ba3c709b6'
down_revision = 'dd7b74eca352'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    new_table = op.create_table('indoor_link_valves',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('thermostat_link_id', sa.Integer(), nullable=True),
    sa.Column('valve_id', sa.Integer(), nullable=False),
    sa.Column('mode', sa.String(length=255), nullable=False),
    sa.ForeignKeyConstraint(['thermostat_link_id'], ['thermostat.id'], name=op.f('fk_indoor_link_valves_thermostat_link_id_thermostat'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['valve_id'], ['valve.id'], name=op.f('fk_indoor_link_valves_valve_id_valve'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_indoor_link_valves')),
    sqlite_autoincrement=True
    )
    # ### end Alembic commands ###

    # ### start migrate old data into new table ###
    # fetch old data
    conn = op.get_bind()
    res = conn.execute("select thermostat_id, valve_id, mode from valvetothermostat")
    results = res.fetchall()

    # Prepare an old_info object to insert into the new table.
    old_info = [{'thermostat_link_id': r[0], 'valve_id': r[1], 'mode': r[2]} for r in results]

    # Insert old_info into new farminfo table.
    op.bulk_insert(new_table, old_info)

    # ### end migrate old data into new table ###

    op.drop_table('valvetothermostat')


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('valvetothermostat',
    sa.Column('thermostat_id', sa.INTEGER(), nullable=False),
    sa.Column('valve_id', sa.INTEGER(), nullable=False),
    sa.Column('mode', sa.VARCHAR(length=255), nullable=False),
    sa.Column('priority', sa.INTEGER(), nullable=False),
    sa.ForeignKeyConstraint(['thermostat_id'], ['thermostat.id'], name='fk_valvetothermostat_thermostat_id_thermostat', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['valve_id'], ['valve.id'], name='fk_valvetothermostat_valve_id_valve', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('thermostat_id', 'valve_id', 'mode', name='pk_valvetothermostat')
    )
    op.drop_table('indoor_link_valves')
    # ### end Alembic commands ###