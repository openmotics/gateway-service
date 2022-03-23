"""initial

Revision ID: 5349e3b38b61
Revises: 
Create Date: 2022-03-22 15:55:43.624985

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5349e3b38b61'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    migrate_existing = sa.inspect(conn.engine).has_table('migratehistory')

    if migrate_existing:
        op.rename_table('apartment', 'apartment_peewee_tmp')
        op.rename_table('config', 'config_peewee_tmp')
        op.rename_table('datamigration', 'datamigration_peewee_tmp')
        op.rename_table('feature', 'feature_peewee_tmp')
        op.rename_table('groupaction', 'groupaction_peewee_tmp')
        op.rename_table('module', 'module_peewee_tmp')
        op.rename_table('plugin', 'plugin_peewee_tmp')
        op.rename_table('room', 'room_peewee_tmp')
        op.rename_table('schedule', 'schedule_peewee_tmp')
        op.rename_table('energymodule', 'energymodule_peewee_tmp')
        op.rename_table('energyct', 'energyct_peewee_tmp')
        op.rename_table('input', 'input_peewee_tmp')
        op.rename_table('output', 'output_peewee_tmp')
        op.rename_table('pulsecounter', 'pulsecounter_peewee_tmp')
        op.rename_table('sensor', 'sensor_peewee_tmp')
        op.rename_table('shutter', 'shutter_peewee_tmp')
        op.rename_table('shuttergroup', 'shuttergroup_peewee_tmp')
        op.rename_table('user', 'user_peewee_tmp')
        op.rename_table('ventilation', 'ventilation_peewee_tmp')
        op.rename_table('delivery', 'delivery_peewee_tmp')
        op.rename_table('pump', 'pump_peewee_tmp')
        op.rename_table('rfid', 'rfid_peewee_tmp')
        op.rename_table('thermostatgroup', 'thermostatgroup_peewee_tmp')
        op.rename_table('valve', 'valve_peewee_tmp')
        op.rename_table('outputtothermostatgroup', 'outputtothermostatgroup_peewee_tmp')
        op.rename_table('pumptovalve', 'pumptovalve_peewee_tmp')
        op.rename_table('thermostat', 'thermostat_peewee_tmp')
        op.rename_table('dayschedule', 'dayschedule_peewee_tmp')
        op.rename_table('preset', 'preset_peewee_tmp')
        op.rename_table('valvetothermostat', 'valvetothermostat_peewee_tmp')

    config = op.create_table('config',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('setting', sa.String(length=255), nullable=False),
    sa.Column('data', sa.String(length=255), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_config')),
    sa.UniqueConstraint('setting', name=op.f('uq_config_setting')),
    sqlite_autoincrement=True
    )
    datamigration = op.create_table('datamigration',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('migrated', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_datamigration')),
    sqlite_autoincrement=True
    )
    feature = op.create_table('feature',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_feature')),
    sa.UniqueConstraint('name', name=op.f('uq_feature_name')),
    sqlite_autoincrement=True
    )
    groupaction = op.create_table('groupaction',
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_groupaction')),
    sa.UniqueConstraint('number', name=op.f('uq_groupaction_number')),
    sqlite_autoincrement=True
    )
    module = op.create_table('module',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('source', sa.String(length=255), nullable=False),
    sa.Column('address', sa.String(length=255), nullable=False),
    sa.Column('module_type', sa.String(length=255), nullable=True),
    sa.Column('hardware_type', sa.String(length=255), nullable=False),
    sa.Column('firmware_version', sa.String(length=255), nullable=True),
    sa.Column('hardware_version', sa.String(length=255), nullable=True),
    sa.Column('order', sa.Integer(), nullable=True),
    sa.Column('last_online_update', sa.Integer(), nullable=True),
    sa.Column('update_success', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_module')),
    sqlite_autoincrement=True
    )
    plugin = op.create_table('plugin',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('version', sa.String(length=255), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_plugin')),
    sa.UniqueConstraint('name', name=op.f('uq_plugin_name')),
    sqlite_autoincrement=True
    )
    room = op.create_table('room',
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=255), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_room')),
    sa.UniqueConstraint('number', name=op.f('uq_room_number')),
    sqlite_autoincrement=True
    )
    schedule = op.create_table('schedule',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('source', sa.String(length=255), nullable=False),
    sa.Column('external_id', sa.String(length=255), nullable=True),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('start', sa.Float(), nullable=False),
    sa.Column('repeat', sa.String(length=255), nullable=True),
    sa.Column('duration', sa.Float(), nullable=True),
    sa.Column('end', sa.Float(), nullable=True),
    sa.Column('action', sa.String(length=255), nullable=False),
    sa.Column('arguments', sa.String(length=255), nullable=True),
    sa.Column('status', sa.String(length=255), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_schedule')),
    sa.UniqueConstraint('source', 'external_id', name=op.f('uq_schedule_source')),
    sqlite_autoincrement=True
    )
    energymodule = op.create_table('energymodule',
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('module_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['module_id'], ['module.id'], name=op.f('fk_energymodule_module_id_module'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_energymodule')),
    sa.UniqueConstraint('module_id', name=op.f('uq_energymodule_module_id')),
    sa.UniqueConstraint('number', name=op.f('uq_energymodule_number')),
    sqlite_autoincrement=True
    )
    energyct = op.create_table('energyct',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('sensor_type', sa.Integer(), nullable=False),
    sa.Column('times', sa.String(length=255), nullable=False),
    sa.Column('inverted', sa.Boolean(), nullable=False),
    sa.Column('energy_module_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['energy_module_id'], ['energymodule.id'], name=op.f('fk_energyct_energy_module_id_energymodule'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_energyct')),
    sa.UniqueConstraint('number', 'energy_module_id', name=op.f('uq_energyct_number')),
    sqlite_autoincrement=True
    )
    input = op.create_table('input',
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('event_enabled', sa.Boolean(), nullable=False),
    sa.Column('room_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['room_id'], ['room.id'], name=op.f('fk_input_room_id_room'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_input')),
    sa.UniqueConstraint('number', name=op.f('uq_input_number')),
    sqlite_autoincrement=True
    )
    output = op.create_table('output',
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('room_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['room_id'], ['room.id'], name=op.f('fk_output_room_id_room'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_output')),
    sa.UniqueConstraint('number', name=op.f('uq_output_number')),
    sqlite_autoincrement=True
    )
    pulsecounter = op.create_table('pulsecounter',
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('source', sa.String(length=255), nullable=False),
    sa.Column('persistent', sa.Boolean(), nullable=False),
    sa.Column('room_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['room_id'], ['room.id'], name=op.f('fk_pulsecounter_room_id_room'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_pulsecounter')),
    sa.UniqueConstraint('number', name=op.f('uq_pulsecounter_number')),
    sqlite_autoincrement=True
    )
    sensor = op.create_table('sensor',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('source', sa.String(length=255), nullable=False),
    sa.Column('external_id', sa.String(length=255), nullable=False),
    sa.Column('physical_quantity', sa.String(length=255), nullable=True),
    sa.Column('unit', sa.String(length=255), nullable=True),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('room_id', sa.Integer(), nullable=True),
    sa.Column('plugin_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['plugin_id'], ['plugin.id'], name=op.f('fk_sensor_plugin_id_plugin'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['room_id'], ['room.id'], name=op.f('fk_sensor_room_id_room'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sensor')),
    sa.UniqueConstraint('source', 'plugin_id', 'external_id', 'physical_quantity', name=op.f('uq_sensor_source')),
    sqlite_autoincrement=True
    )
    shutter = op.create_table('shutter',
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('room_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['room_id'], ['room.id'], name=op.f('fk_shutter_room_id_room'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_shutter')),
    sa.UniqueConstraint('number', name=op.f('uq_shutter_number')),
    sqlite_autoincrement=True
    )
    shuttergroup = op.create_table('shuttergroup',
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('room_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['room_id'], ['room.id'], name=op.f('fk_shuttergroup_room_id_room'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_shuttergroup')),
    sa.UniqueConstraint('number', name=op.f('uq_shuttergroup_number')),
    sqlite_autoincrement=True
    )
    user = op.create_table('user',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('username', sa.String(length=255), nullable=False),
    sa.Column('first_name', sa.String(length=255), nullable=True),
    sa.Column('last_name', sa.String(length=255), nullable=True),
    sa.Column('role', sa.String(length=255), nullable=False),
    sa.Column('pin_code', sa.String(length=255), nullable=True),
    sa.Column('language', sa.String(length=255), nullable=False),
    sa.Column('password', sa.String(length=255), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('accepted_terms', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_user')),
    sa.UniqueConstraint('pin_code', name=op.f('uq_user_pin_code')),
    sa.UniqueConstraint('username', name=op.f('uq_user_username')),
    sqlite_autoincrement=True
    )
    ventilation = op.create_table('ventilation',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('source', sa.String(length=255), nullable=False),
    sa.Column('plugin_id', sa.Integer(), nullable=True),
    sa.Column('external_id', sa.String(length=255), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('amount_of_levels', sa.Integer(), nullable=False),
    sa.Column('device_vendor', sa.String(length=255), nullable=False),
    sa.Column('device_type', sa.String(length=255), nullable=False),
    sa.Column('device_serial', sa.String(length=255), nullable=False),
    sa.ForeignKeyConstraint(['plugin_id'], ['plugin.id'], name=op.f('fk_ventilation_plugin_id_plugin'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ventilation')),
    sa.UniqueConstraint('source', 'plugin_id', 'external_id', name=op.f('uq_ventilation_source')),
    sqlite_autoincrement=True
    )
    pump = op.create_table('pump',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('output_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['output_id'], ['output.id'], name=op.f('fk_pump_output_id_output'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_pump')),
    sa.UniqueConstraint('output_id', name=op.f('uq_pump_output_id')),
    sqlite_autoincrement=True
    )
    thermostatgroup = op.create_table('thermostatgroup',
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('threshold_temperature', sa.Float(), nullable=True),
    sa.Column('sensor_id', sa.Integer(), nullable=True),
    sa.Column('mode', sa.String(length=255), nullable=False),
    sa.ForeignKeyConstraint(['sensor_id'], ['sensor.id'], name=op.f('fk_thermostatgroup_sensor_id_sensor'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_thermostatgroup')),
    sa.UniqueConstraint('number', name=op.f('uq_thermostatgroup_number')),
    sqlite_autoincrement=True
    )
    valve = op.create_table('valve',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('delay', sa.Integer(), nullable=False),
    sa.Column('output_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['output_id'], ['output.id'], name=op.f('fk_valve_output_id_output'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_valve')),
    sa.UniqueConstraint('output_id', name=op.f('uq_valve_output_id')),
    sqlite_autoincrement=True
    )
    outputtothermostatgroup = op.create_table('outputtothermostatgroup',
    sa.Column('output_id', sa.Integer(), nullable=False),
    sa.Column('thermostat_group_id', sa.Integer(), nullable=False),
    sa.Column('mode', sa.String(length=255), nullable=False),
    sa.Column('index', sa.Integer(), nullable=False),
    sa.Column('value', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['output_id'], ['output.id'], name=op.f('fk_outputtothermostatgroup_output_id_output'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['thermostat_group_id'], ['thermostatgroup.id'], name=op.f('fk_outputtothermostatgroup_thermostat_group_id_thermostatgroup'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('output_id', 'thermostat_group_id', 'mode', name=op.f('pk_outputtothermostatgroup')),
    sqlite_autoincrement=True
    )
    pumptovalve = op.create_table('pumptovalve',
    sa.Column('pump_id', sa.Integer(), nullable=False),
    sa.Column('valve_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['pump_id'], ['pump.id'], name=op.f('fk_pumptovalve_pump_id_pump'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['valve_id'], ['valve.id'], name=op.f('fk_pumptovalve_valve_id_valve'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('pump_id', 'valve_id', name=op.f('pk_pumptovalve')),
    sqlite_autoincrement=True
    )
    thermostat = op.create_table('thermostat',
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('state', sa.String(length=255), nullable=False),
    sa.Column('sensor_id', sa.Integer(), nullable=True),
    sa.Column('pid_heating_p', sa.Float(), nullable=False),
    sa.Column('pid_heating_i', sa.Float(), nullable=False),
    sa.Column('pid_heating_d', sa.Float(), nullable=False),
    sa.Column('pid_cooling_p', sa.Float(), nullable=False),
    sa.Column('pid_cooling_i', sa.Float(), nullable=False),
    sa.Column('pid_cooling_d', sa.Float(), nullable=False),
    sa.Column('automatic', sa.Boolean(), nullable=False),
    sa.Column('room_id', sa.Integer(), nullable=True),
    sa.Column('start', sa.Integer(), nullable=False),
    sa.Column('valve_config', sa.String(length=255), nullable=False),
    sa.Column('thermostat_group_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['room_id'], ['room.id'], name=op.f('fk_thermostat_room_id_room'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['sensor_id'], ['sensor.id'], name=op.f('fk_thermostat_sensor_id_sensor'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['thermostat_group_id'], ['thermostatgroup.id'], name=op.f('fk_thermostat_thermostat_group_id_thermostatgroup'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_thermostat')),
    sa.UniqueConstraint('number', name=op.f('uq_thermostat_number')),
    sqlite_autoincrement=True
    )
    dayschedule = op.create_table('dayschedule',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('index', sa.Integer(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('mode', sa.String(length=255), nullable=False),
    sa.Column('thermostat_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['thermostat_id'], ['thermostat.id'], name=op.f('fk_dayschedule_thermostat_id_thermostat'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_dayschedule')),
    sqlite_autoincrement=True
    )
    preset = op.create_table('preset',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('type', sa.String(length=255), nullable=False),
    sa.Column('heating_setpoint', sa.Float(), nullable=False),
    sa.Column('cooling_setpoint', sa.Float(), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('thermostat_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['thermostat_id'], ['thermostat.id'], name=op.f('fk_preset_thermostat_id_thermostat'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_preset')),
    sqlite_autoincrement=True
    )
    valvetothermostat = op.create_table('valvetothermostat',
    sa.Column('thermostat_id', sa.Integer(), nullable=False),
    sa.Column('valve_id', sa.Integer(), nullable=False),
    sa.Column('mode', sa.String(length=255), nullable=False),
    sa.Column('priority', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['thermostat_id'], ['thermostat.id'], name=op.f('fk_valvetothermostat_thermostat_id_thermostat'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['valve_id'], ['valve.id'], name=op.f('fk_valvetothermostat_valve_id_valve'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('thermostat_id', 'valve_id', 'mode', name=op.f('pk_valvetothermostat')),
    sqlite_autoincrement=True
    )

    if migrate_existing:
        for t, table_name in [(config, 'config_peewee_tmp'),
                              (datamigration, 'datamigration_peewee_tmp'),
                              (feature, 'feature_peewee_tmp'),
                              (groupaction, 'groupaction_peewee_tmp'),
                              (module, 'module_peewee_tmp'),
                              (plugin, 'plugin_peewee_tmp'),
                              (room, 'room_peewee_tmp'),
                              (schedule, 'schedule_peewee_tmp'),
                              (energymodule, 'energymodule_peewee_tmp'),
                              (energyct, 'energyct_peewee_tmp'),
                              (input, 'input_peewee_tmp'),
                              (output, 'output_peewee_tmp'),
                              (pulsecounter, 'pulsecounter_peewee_tmp'),
                              (sensor, 'sensor_peewee_tmp'),
                              (shutter, 'shutter_peewee_tmp'),
                              (shuttergroup, 'shuttergroup_peewee_tmp'),
                              (user, 'user_peewee_tmp'),
                              (ventilation, 'ventilation_peewee_tmp'),
                              (pump, 'pump_peewee_tmp'),
                              (thermostatgroup, 'thermostatgroup_peewee_tmp'),
                              (valve, 'valve_peewee_tmp'),
                              (outputtothermostatgroup, 'outputtothermostatgroup_peewee_tmp'),
                              (pumptovalve, 'pumptovalve_peewee_tmp'),
                              (thermostat, 'thermostat_peewee_tmp'),
                              (dayschedule, 'dayschedule_peewee_tmp'),
                              (preset, 'preset_peewee_tmp'),
                              (valvetothermostat, 'valvetothermostat_peewee_tmp')]:
            resultset = conn.execute('SELECT * FROM {0}'.format(table_name))
            op.bulk_insert(t, [dict(x) for x in resultset.mappings().all()])  # type: ignore

        with op.batch_alter_table('pump_peewee_tmp', schema=None) as batch_op:
            batch_op.drop_index('pump_output_id')
        op.drop_table('pump_peewee_tmp')
        with op.batch_alter_table('shuttergroup_peewee_tmp', schema=None) as batch_op:
            batch_op.drop_index('shuttergroup_number')
            batch_op.drop_index('shuttergroup_room_id')
        op.drop_table('shuttergroup_peewee_tmp')
        with op.batch_alter_table('feature_peewee_tmp', schema=None) as batch_op:
            batch_op.drop_index('feature_name')
        op.drop_table('feature_peewee_tmp')
        with op.batch_alter_table('input_peewee_tmp', schema=None) as batch_op:
            batch_op.drop_index('input_number')
            batch_op.drop_index('input_room_id')
        op.drop_table('input_peewee_tmp')
        with op.batch_alter_table('thermostatgroup_peewee_tmp', schema=None) as batch_op:
            batch_op.drop_index('thermostatgroup_number')
            batch_op.drop_index('thermostatgroup_sensor_id')
        op.drop_table('thermostatgroup_peewee_tmp')
        with op.batch_alter_table('groupaction_peewee_tmp', schema=None) as batch_op:
            batch_op.drop_index('groupaction_number')
        op.drop_table('groupaction_peewee_tmp')
        with op.batch_alter_table('schedule_peewee_tmp', schema=None) as batch_op:
            batch_op.drop_index('schedule_source_external_id')
        op.drop_table('schedule_peewee_tmp')
        with op.batch_alter_table('ventilation_peewee_tmp', schema=None) as batch_op:
            batch_op.drop_index('ventilation_plugin_id')
            batch_op.drop_index('ventilation_source_plugin_id_external_id')
        op.drop_table('ventilation_peewee_tmp')
        with op.batch_alter_table('dayschedule_peewee_tmp', schema=None) as batch_op:
            batch_op.drop_index('dayschedule_thermostat_id')
        op.drop_table('dayschedule_peewee_tmp')
        with op.batch_alter_table('plugin_peewee_tmp', schema=None) as batch_op:
            batch_op.drop_index('plugin_name')
        op.drop_table('plugin_peewee_tmp')
        op.drop_table('datamigration_peewee_tmp')
        with op.batch_alter_table('apartment_peewee_tmp', schema=None) as batch_op:
            batch_op.drop_index('apartment_doorbell_rebus_id')
            batch_op.drop_index('apartment_mailbox_rebus_id')
        op.drop_table('apartment_peewee_tmp')
        with op.batch_alter_table('shutter_peewee_tmp', schema=None) as batch_op:
            batch_op.drop_index('shutter_number')
            batch_op.drop_index('shutter_room_id')
        op.drop_table('shutter_peewee_tmp')
        with op.batch_alter_table('preset_peewee_tmp', schema=None) as batch_op:
            batch_op.drop_index('preset_thermostat_id')
        op.drop_table('preset_peewee_tmp')
        with op.batch_alter_table('room_peewee_tmp', schema=None) as batch_op:
            batch_op.drop_index('room_number')
        op.drop_table('room_peewee_tmp')
        with op.batch_alter_table('rfid_peewee_tmp', schema=None) as batch_op:
            batch_op.drop_index('rfid_tag_string')
            batch_op.drop_index('rfid_uid_manufacturer')
            batch_op.drop_index('rfid_user_id')
        op.drop_table('rfid_peewee_tmp')
        with op.batch_alter_table('pumptovalve_peewee_tmp', schema=None) as batch_op:
            batch_op.drop_index('pumptovalve_pump_id')
            batch_op.drop_index('pumptovalve_pump_id_valve_id')
            batch_op.drop_index('pumptovalve_valve_id')
        op.drop_table('pumptovalve_peewee_tmp')
        with op.batch_alter_table('user_peewee_tmp', schema=None) as batch_op:
            batch_op.drop_index('user_apartment_id')
            batch_op.drop_index('user_pin_code')
        with op.batch_alter_table('config_peewee_tmp', schema=None) as batch_op:
            batch_op.drop_index('config_setting')
        op.drop_table('config_peewee_tmp')
        with op.batch_alter_table('pulsecounter_peewee_tmp', schema=None) as batch_op:
            batch_op.drop_index('pulsecounter_number')
            batch_op.drop_index('pulsecounter_room_id')
        op.drop_table('pulsecounter_peewee_tmp')
        with op.batch_alter_table('valvetothermostat_peewee_tmp', schema=None) as batch_op:
            batch_op.drop_index('valvetothermostat_thermostat_id')
            batch_op.drop_index('valvetothermostat_valve_id')
            batch_op.drop_index('valvetothermostat_valve_id_thermostat_id_mode')
        op.drop_table('valvetothermostat_peewee_tmp')
        with op.batch_alter_table('delivery_peewee_tmp', schema=None) as batch_op:
            batch_op.drop_index('delivery_user_delivery_tmp_id')
            batch_op.drop_index('delivery_user_pickup_tmp_id')
        op.drop_table('delivery_peewee_tmp')
        with op.batch_alter_table('output_peewee_tmp', schema=None) as batch_op:
            batch_op.drop_index('output_number')
            batch_op.drop_index('output_room_id')
        op.drop_table('output_peewee_tmp')
        with op.batch_alter_table('sensor_peewee_tmp', schema=None) as batch_op:
            batch_op.drop_index('sensor_plugin_id')
            batch_op.drop_index('sensor_room_id')
            batch_op.drop_index('sensor_source_plugin_id_external_id_physical_quantity')
        op.drop_table('sensor_peewee_tmp')
        with op.batch_alter_table('valve_peewee_tmp', schema=None) as batch_op:
            batch_op.drop_index('valve_output_id')
        op.drop_table('valve_peewee_tmp')
        with op.batch_alter_table('thermostat_peewee_tmp', schema=None) as batch_op:
            batch_op.drop_index('thermostat_number')
            batch_op.drop_index('thermostat_room_id')
            batch_op.drop_index('thermostat_sensor_id')
            batch_op.drop_index('thermostat_thermostat_group_id')
        op.drop_table('thermostat_peewee_tmp')
        with op.batch_alter_table('outputtothermostatgroup_peewee_tmp', schema=None) as batch_op:
            batch_op.drop_index('outputtothermostatgroup_output_id')
            batch_op.drop_index('outputtothermostatgroup_output_id_thermostat_group_id_mode')
            batch_op.drop_index('outputtothermostatgroup_thermostat_group_id')
        op.drop_table('outputtothermostatgroup_peewee_tmp')
        with op.batch_alter_table('energyct_peewee_tmp', schema=None) as batch_op:
            batch_op.drop_index('energyct_energy_module_id')
            batch_op.drop_index('energyct_number_energy_module_id')
        op.drop_table('energyct_peewee_tmp')
        with op.batch_alter_table('energymodule_peewee_tmp', schema=None) as batch_op:
            batch_op.drop_index('energymodule_module_id')
            batch_op.drop_index('energymodule_number')
        op.drop_table('energymodule_peewee_tmp')
        op.drop_table('module_peewee_tmp')
        op.drop_table('user_peewee_tmp')

        op.drop_table('migratehistory')


def downgrade():
    raise NotImplementedError()
