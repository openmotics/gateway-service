# Copyright (C) 2020 OpenMotics BV
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
import time
from datetime import timedelta

from gateway.migrations.base_migrator import BaseMigrator
from gateway.models import Database, DaySchedule, Feature, Output, \
    OutputToThermostatGroupAssociation, Preset, Pump, PumpToValveAssociation, Room, Sensor, \
    Thermostat, ThermostatGroup, Valve, ValveToThermostatAssociation, Session
from ioc import INJECTED, Inject
from master.classic import master_api
from master.classic.eeprom_controller import CompositeDataType, EepromByte, \
    EepromCSV, EepromIBool, EepromId, EepromModel, EepromString, EepromTemp, \
    EepromTime, EextByte
from platform_utils import Platform

if False:  # MYPY
    from typing import Any, List, Iterable, Tuple
    from master.classic.eeprom_controller import EepromController
    from master.classic.master_communicator import MasterCommunicator

logger = logging.getLogger(__name__)


class GlobalThermostatConfiguration(EepromModel):
    """ The global thermostat configuration. """
    outside_sensor = EepromByte((0, 16))
    threshold_temp = EepromTemp((0, 17))
    pump_delay = EepromByte((0, 19))
    switch_to_heating_output_0 = EepromByte((199, 0))
    switch_to_heating_value_0 = EepromByte((199, 1))
    switch_to_heating_output_1 = EepromByte((199, 2))
    switch_to_heating_value_1 = EepromByte((199, 3))
    switch_to_heating_output_2 = EepromByte((199, 4))
    switch_to_heating_value_2 = EepromByte((199, 5))
    switch_to_heating_output_3 = EepromByte((199, 6))
    switch_to_heating_value_3 = EepromByte((199, 7))
    switch_to_cooling_output_0 = EepromByte((199, 8))
    switch_to_cooling_value_0 = EepromByte((199, 9))
    switch_to_cooling_output_1 = EepromByte((199, 10))
    switch_to_cooling_value_1 = EepromByte((199, 11))
    switch_to_cooling_output_2 = EepromByte((199, 12))
    switch_to_cooling_value_2 = EepromByte((199, 13))
    switch_to_cooling_output_3 = EepromByte((199, 14))
    switch_to_cooling_value_3 = EepromByte((199, 15))


class ThermostatConfiguration(EepromModel):
    """ Models a thermostat. The maximum number of thermostats is 32. """
    id = EepromId(32)  # type: ignore
    name = EepromString(16, lambda mid: (187 + (mid / 16), 16 * (mid % 16)))
    setp0 = EepromTemp(lambda mid: (142, 32 + mid))
    setp1 = EepromTemp(lambda mid: (142, 64 + mid))
    setp2 = EepromTemp(lambda mid: (142, 96 + mid))
    setp3 = EepromTemp(lambda mid: (142, 128 + mid))
    setp4 = EepromTemp(lambda mid: (142, 160 + mid))
    setp5 = EepromTemp(lambda mid: (142, 192 + mid))
    sensor = EepromByte(lambda mid: (144, 8 + mid))
    output0 = EepromByte(lambda mid: (142, mid))
    output1 = EepromByte(lambda mid: (142, 224 + mid))
    pid_p = EepromByte(lambda mid: (141, 4 * mid))
    pid_i = EepromByte(lambda mid: (141, (4 * mid) + 1))
    pid_d = EepromByte(lambda mid: (141, (4 * mid) + 2))
    pid_int = EepromByte(lambda mid: (141, (4 * mid) + 3))
    permanent_manual = EepromIBool(lambda mid: (195, 32 + mid))
    auto_mon = CompositeDataType([
        ('temp_n', EepromTemp(lambda mid: (198, mid + 0))),
        ('start_d1', EepromTime(lambda mid: (189, (4 * mid) + 0))),
        ('stop_d1', EepromTime(lambda mid: (189, (4 * mid) + 1))),
        ('temp_d1', EepromTemp(lambda mid: (196, mid + 0))),
        ('start_d2', EepromTime(lambda mid: (189, (4 * mid) + 2))),
        ('stop_d2', EepromTime(lambda mid: (189, (4 * mid) + 3))),
        ('temp_d2', EepromTemp(lambda mid: (197, mid + 0)))
    ])
    auto_tue = CompositeDataType([
        ('temp_n', EepromTemp(lambda mid: (198, mid + 32))),
        ('start_d1', EepromTime(lambda mid: (189, (4 * mid) + 128))),
        ('stop_d1', EepromTime(lambda mid: (189, (4 * mid) + 129))),
        ('temp_d1', EepromTemp(lambda mid: (196, mid + 32))),
        ('start_d2', EepromTime(lambda mid: (189, (4 * mid) + 130))),
        ('stop_d2', EepromTime(lambda mid: (189, (4 * mid) + 131))),
        ('temp_d2', EepromTemp(lambda mid: (197, mid + 32)))
    ])
    auto_wed = CompositeDataType([
        ('temp_n', EepromTemp(lambda mid: (198, mid + 64))),
        ('start_d1', EepromTime(lambda mid: (190, (4 * mid) + 0))),
        ('stop_d1', EepromTime(lambda mid: (190, (4 * mid) + 1))),
        ('temp_d1', EepromTemp(lambda mid: (196, mid + 64))),
        ('start_d2', EepromTime(lambda mid: (190, (4 * mid) + 2))),
        ('stop_d2', EepromTime(lambda mid: (190, (4 * mid) + 3))),
        ('temp_d2', EepromTemp(lambda mid: (197, mid + 64)))
    ])
    auto_thu = CompositeDataType([
        ('temp_n', EepromTemp(lambda mid: (198, mid + 96))),
        ('start_d1', EepromTime(lambda mid: (190, (4 * mid) + 128))),
        ('stop_d1', EepromTime(lambda mid: (190, (4 * mid) + 129))),
        ('temp_d1', EepromTemp(lambda mid: (196, mid + 96))),
        ('start_d2', EepromTime(lambda mid: (190, (4 * mid) + 130))),
        ('stop_d2', EepromTime(lambda mid: (190, (4 * mid) + 131))),
        ('temp_d2', EepromTemp(lambda mid: (197, mid + 96)))
    ])
    auto_fri = CompositeDataType([
        ('temp_n', EepromTemp(lambda mid: (198, mid + 128))),
        ('start_d1', EepromTime(lambda mid: (191, (4 * mid) + 0))),
        ('stop_d1', EepromTime(lambda mid: (191, (4 * mid) + 1))),
        ('temp_d1', EepromTemp(lambda mid: (196, mid + 128))),
        ('start_d2', EepromTime(lambda mid: (191, (4 * mid) + 2))),
        ('stop_d2', EepromTime(lambda mid: (191, (4 * mid) + 3))),
        ('temp_d2', EepromTemp(lambda mid: (197, mid + 128)))
    ])
    auto_sat = CompositeDataType([
        ('temp_n', EepromTemp(lambda mid: (198, mid + 160))),
        ('start_d1', EepromTime(lambda mid: (191, (4 * mid) + 128))),
        ('stop_d1', EepromTime(lambda mid: (191, (4 * mid) + 129))),
        ('temp_d1', EepromTemp(lambda mid: (196, mid + 160))),
        ('start_d2', EepromTime(lambda mid: (191, (4 * mid) + 130))),
        ('stop_d2', EepromTime(lambda mid: (191, (4 * mid) + 131))),
        ('temp_d2', EepromTemp(lambda mid: (197, mid + 160)))
    ])
    auto_sun = CompositeDataType([
        ('temp_n', EepromTemp(lambda mid: (198, mid + 192))),
        ('start_d1', EepromTime(lambda mid: (192, (4 * mid) + 0))),
        ('stop_d1', EepromTime(lambda mid: (192, (4 * mid) + 1))),
        ('temp_d1', EepromTemp(lambda mid: (196, mid + 192))),
        ('start_d2', EepromTime(lambda mid: (192, (4 * mid) + 2))),
        ('stop_d2', EepromTime(lambda mid: (192, (4 * mid) + 3))),
        ('temp_d2', EepromTemp(lambda mid: (197, mid + 192)))
    ])
    room = EextByte()


class CoolingConfiguration(EepromModel):
    """ Models a thermostat in cooling mode. The maximum number of thermostats is 32. """
    id = EepromId(32)  # type: ignore
    name = EepromString(16, lambda mid: (204 + (mid / 16), 16 * (mid % 16)))
    setp0 = EepromTemp(lambda mid: (201, 32 + mid))
    setp1 = EepromTemp(lambda mid: (201, 64 + mid))
    setp2 = EepromTemp(lambda mid: (201, 96 + mid))
    setp3 = EepromTemp(lambda mid: (201, 128 + mid))
    setp4 = EepromTemp(lambda mid: (201, 160 + mid))
    setp5 = EepromTemp(lambda mid: (201, 192 + mid))
    sensor = EepromByte(lambda mid: (203, 8 + mid))
    output0 = EepromByte(lambda mid: (201, mid))
    output1 = EepromByte(lambda mid: (201, 224 + mid))
    pid_p = EepromByte(lambda mid: (200, 4 * mid))
    pid_i = EepromByte(lambda mid: (200, (4 * mid) + 1))
    pid_d = EepromByte(lambda mid: (200, (4 * mid) + 2))
    pid_int = EepromByte(lambda mid: (200, (4 * mid) + 3))
    permanent_manual = EepromIBool(lambda mid: (195, 64 + mid))
    auto_mon = CompositeDataType([
        ('temp_n', EepromTemp(lambda mid: (212, mid + 0))),
        ('start_d1', EepromTime(lambda mid: (206, (4 * mid) + 0))),
        ('stop_d1', EepromTime(lambda mid: (206, (4 * mid) + 1))),
        ('temp_d1', EepromTemp(lambda mid: (210, mid + 0))),
        ('start_d2', EepromTime(lambda mid: (206, (4 * mid) + 2))),
        ('stop_d2', EepromTime(lambda mid: (206, (4 * mid) + 3))),
        ('temp_d2', EepromTemp(lambda mid: (211, mid + 0)))
    ])
    auto_tue = CompositeDataType([
        ('temp_n', EepromTemp(lambda mid: (212, mid + 32))),
        ('start_d1', EepromTime(lambda mid: (206, (4 * mid) + 128))),
        ('stop_d1', EepromTime(lambda mid: (206, (4 * mid) + 129))),
        ('temp_d1', EepromTemp(lambda mid: (210, mid + 32))),
        ('start_d2', EepromTime(lambda mid: (206, (4 * mid) + 130))),
        ('stop_d2', EepromTime(lambda mid: (206, (4 * mid) + 131))),
        ('temp_d2', EepromTemp(lambda mid: (211, mid + 32)))
    ])
    auto_wed = CompositeDataType([
        ('temp_n', EepromTemp(lambda mid: (212, mid + 64))),
        ('start_d1', EepromTime(lambda mid: (207, (4 * mid) + 0))),
        ('stop_d1', EepromTime(lambda mid: (207, (4 * mid) + 1))),
        ('temp_d1', EepromTemp(lambda mid: (210, mid + 64))),
        ('start_d2', EepromTime(lambda mid: (207, (4 * mid) + 2))),
        ('stop_d2', EepromTime(lambda mid: (207, (4 * mid) + 3))),
        ('temp_d2', EepromTemp(lambda mid: (211, mid + 64)))
    ])
    auto_thu = CompositeDataType([
        ('temp_n', EepromTemp(lambda mid: (212, mid + 96))),
        ('start_d1', EepromTime(lambda mid: (207, (4 * mid) + 128))),
        ('stop_d1', EepromTime(lambda mid: (207, (4 * mid) + 129))),
        ('temp_d1', EepromTemp(lambda mid: (210, mid + 96))),
        ('start_d2', EepromTime(lambda mid: (207, (4 * mid) + 130))),
        ('stop_d2', EepromTime(lambda mid: (207, (4 * mid) + 131))),
        ('temp_d2', EepromTemp(lambda mid: (211, mid + 96)))
    ])
    auto_fri = CompositeDataType([
        ('temp_n', EepromTemp(lambda mid: (212, mid + 128))),
        ('start_d1', EepromTime(lambda mid: (208, (4 * mid) + 0))),
        ('stop_d1', EepromTime(lambda mid: (208, (4 * mid) + 1))),
        ('temp_d1', EepromTemp(lambda mid: (210, mid + 128))),
        ('start_d2', EepromTime(lambda mid: (208, (4 * mid) + 2))),
        ('stop_d2', EepromTime(lambda mid: (208, (4 * mid) + 3))),
        ('temp_d2', EepromTemp(lambda mid: (211, mid + 128)))
    ])
    auto_sat = CompositeDataType([
        ('temp_n', EepromTemp(lambda mid: (212, mid + 160))),
        ('start_d1', EepromTime(lambda mid: (208, (4 * mid) + 128))),
        ('stop_d1', EepromTime(lambda mid: (208, (4 * mid) + 129))),
        ('temp_d1', EepromTemp(lambda mid: (210, mid + 160))),
        ('start_d2', EepromTime(lambda mid: (208, (4 * mid) + 130))),
        ('stop_d2', EepromTime(lambda mid: (208, (4 * mid) + 131))),
        ('temp_d2', EepromTemp(lambda mid: (211, mid + 160)))
    ])
    auto_sun = CompositeDataType([
        ('temp_n', EepromTemp(lambda mid: (212, mid + 192))),
        ('start_d1', EepromTime(lambda mid: (209, (4 * mid) + 0))),
        ('stop_d1', EepromTime(lambda mid: (209, (4 * mid) + 1))),
        ('temp_d1', EepromTemp(lambda mid: (210, mid + 192))),
        ('start_d2', EepromTime(lambda mid: (209, (4 * mid) + 2))),
        ('stop_d2', EepromTime(lambda mid: (209, (4 * mid) + 3))),
        ('temp_d2', EepromTemp(lambda mid: (211, mid + 192)))
    ])
    room = EextByte()


class PumpGroupConfiguration(EepromModel):
    """ Models a pump group. The maximum number of pump groups is 8. """
    id = EepromId(8)  # type: ignore
    outputs = EepromCSV(32, lambda mid: (143, mid * 32))
    output = EepromByte(lambda mid: (144, mid))
    room = EextByte()


class ThermostatsMigrator(BaseMigrator):

    MIGRATION_KEY = 'thermostats'

    HEATING_PID_MAPPING = [
        ('pid_heating_p', 'pid_p', 120),
        ('pid_heating_i', 'pid_i', 0),
        ('pid_heating_d', 'pid_d', 0),
    ]

    COOLING_PID_MAPPING = [
        ('pid_cooling_p', 'pid_p', 120),
        ('pid_cooling_i', 'pid_i', 0),
        ('pid_cooling_d', 'pid_d', 0)
    ]

    PRESET_MAPPING = [
        (Preset.Types.AWAY, 'setp3'),
        (Preset.Types.VACATION, 'setp4'),
        (Preset.Types.PARTY, 'setp5')
    ]

    @classmethod
    def _migrate(cls):
        # Core(+) platforms only support gateway thermostats
        if Platform.get_platform() not in Platform.ClassicTypes:
            return

        # Remove all existing gateway configuration
        with Database.get_session() as db:
            db.query(Thermostat).delete()
            db.query(OutputToThermostatGroupAssociation).delete()
            db.query(Pump).delete()
            db.query(Valve).delete()

            thermostat_group = db.query(ThermostatGroup).limit(1).one()  # TODO: Does this one exists?

            for eeprom_object in cls._read_heating_configuration():
                cls._migrate_thermostat(db, thermostat_group, ThermostatGroup.Modes.HEATING, eeprom_object)
            for eeprom_object in cls._read_cooling_configuration():
                cls._migrate_thermostat(db, thermostat_group, ThermostatGroup.Modes.COOLING, eeprom_object)

            for eeprom_object in cls._read_pump_group_configuration():
                cls._migrate_pump_group(db, eeprom_object)

            eeprom_object = cls._read_global_configuration()
            cls._migrate_thermostat_group(db, thermostat_group, eeprom_object)

            try:
                logger.info('Disabling master Thermostats.')
                cls._disable_master_thermostats()
            except Exception:
                logger.exception('Could not migrate master Thermostats')
                feature = db.query(Feature).get(name=Feature.THERMOSTATS_GATEWAY)
                feature.enabled = False

            db.commit()

    @classmethod
    def _migrate_thermostat(cls, db, thermostat_group, mode, eeprom_object):
        # type: (Session, ThermostatGroup, str, Any) -> None
        if eeprom_object.sensor == 240:
            raise RuntimeError('Thermostat {} with timer only configuration, this can\'t be migrated'.format(eeprom_object.id))
        if eeprom_object.sensor in (None, 255):
            return

        temperature = Sensor.PhysicalQuantities.TEMPERATURE
        sensor = db.query(Sensor).where((Sensor.physical_quantity == temperature) &
                                        (Sensor.external_id == str(eeprom_object.sensor))).one_or_none()
        if sensor is None:
            sensor = db.query(Sensor).where((Sensor.physical_quantity is None) &
                                            (Sensor.external_id == str(eeprom_object.sensor))).one_or_none()
            if sensor is None:
                sensor = Sensor(physical_quantity=temperature,
                                unit=Sensor.Units.CELCIUS,
                                external_id=str(eeprom_object.sensor))
                db.add(sensor)
        if sensor is None:
            raise ValueError('Thermostat <Sensor external_id={}> does not exist'.format(eeprom_object.sensor))
        if sensor.source != Sensor.Sources.MASTER:
            raise ValueError('Unexpected <Sensor {}> {} for thermostats'.format(sensor.id, sensor.source))
        room = db.query(Room).where(Room.number == eeprom_object.room).one_or_none()

        # We don't get a start date, calculate last monday night to map the schedules
        now = int(time.time())
        day_of_week = (now / 86400 - 4) % 7  # 0: Monday, 1: Tuesday, ...
        last_monday_night = now - now % 86400 - day_of_week * 86400

        thermostat = db.query(Thermostat).where(Thermostat.number == eeprom_object.id).one_or_none()
        if thermostat is None:
            kwargs = {'number': eeprom_object.id,
                      'name': eeprom_object.name,
                      'thermostat_group': thermostat_group,
                      'sensor': sensor,
                      'room': room,
                      'start': last_monday_night,
                      'valve_config': Thermostat.ValveConfigs.CASCADE}
            thermostat = Thermostat.create(**kwargs)
            db.add(thermostat)

        cls._migrate_pid_parameters(thermostat, mode, eeprom_object)
        cls._migrate_output(db, thermostat, mode, eeprom_object.output0, 0)
        cls._migrate_output(db, thermostat, mode, eeprom_object.output1, 1)
        cls._migrate_presets(db, thermostat, mode, eeprom_object)
        cls._migrate_schedules(db, thermostat, mode, eeprom_object)

    @classmethod
    def _migrate_pid_parameters(cls, thermostat, mode, eeprom_object):
        # type: (Thermostat, str, Any) -> None
        mapping = cls.HEATING_PID_MAPPING if mode == ThermostatGroup.Modes.HEATING else cls.COOLING_PID_MAPPING
        for dst_field, src_field, default_value in mapping:
            value = getattr(eeprom_object, src_field)
            if value in (None, 255):
                value = default_value
            setattr(thermostat, dst_field, value)

    @classmethod
    def _migrate_output(cls, db, thermostat, mode, output_nr, valve_priority):
        # type: (Session, Thermostat, str, int, int) -> None
        if output_nr not in (None, 255):
            output = db.query(Output).where(Output.number == output_nr).one()
            name = 'Valve (output {0})'.format(output.number)
            valve = db.query(Valve).where(Valve.output == output).one_or_none()
            if valve is None:
                valve = Valve(output=output, name=name)
                db.add(valve)
            else:
                valve.name = name
            valve_to_thermostat = db.query(ValveToThermostatAssociation).where(
                (ValveToThermostatAssociation.mode == mode) &
                (ValveToThermostatAssociation.valve == valve) &
                (ValveToThermostatAssociation.thermostat == thermostat)
            ).one_or_none()
            if valve_to_thermostat is None:
                valve_to_thermostat = ValveToThermostatAssociation(mode=mode,
                                                                   valve=valve,
                                                                   thermostat=thermostat,
                                                                   priority=valve_priority)
                db.add(valve_to_thermostat)
            else:
                valve_to_thermostat.priority = valve_priority

    @classmethod
    def _migrate_presets(cls, db, thermostat, mode, eeprom_object):
        # type: (Session, Thermostat, str, Any) -> None
        for preset_type, src_field in cls.PRESET_MAPPING:
            value = getattr(eeprom_object, src_field)
            if value not in (None, 255):
                preset = db.query(Preset).where(
                    (Preset.thermostat == thermostat) &
                    (Preset.type == preset_type)
                ).one_or_none()
                if preset is None:
                    preset = Preset(thermostat=thermostat,
                                    type=preset_type)
                    db.add(preset)
                if mode == ThermostatGroup.Modes.HEATING:
                    preset.heating_setpoint = value
                else:
                    preset.cooling_setpoint = value

    @classmethod
    def _migrate_schedules(cls, db, thermostat, mode, eeprom_object):
        start_night = 0
        night_end = int(timedelta(hours=24, minutes=0, seconds=0).total_seconds())

        def get_seconds(hour_timestamp):
            # type: (str) -> int
            if hour_timestamp == '24:00':
                return night_end
            else:
                t = time.strptime(hour_timestamp, '%H:%M')
                return int(timedelta(hours=t.tm_hour, minutes=t.tm_min, seconds=t.tm_sec).total_seconds())

        for i, schedule in cls._enumerate_schedules(eeprom_object):
            temp_night = schedule[0]
            start_day_1 = get_seconds(schedule[1])
            end_day_1 = get_seconds(schedule[2])
            temp_day_1 = schedule[3]
            start_day_2 = get_seconds(schedule[4])
            end_day_2 = get_seconds(schedule[5])
            temp_day_2 = schedule[6]

            # Attempt to resolve overlapping transitions in the schedule
            offset = 600
            if start_day_1 <= start_night:
                start_day_1 = start_night + offset
            if end_day_1 <= start_day_1:
                end_day_1 = start_day_1 + offset
            if start_day_2 <= end_day_1:
                start_day_2 = end_day_1 + offset
            if end_day_2 <= start_day_2:
                end_day_2 = start_day_2 + offset
            if end_day_2 >= night_end:
                end_day_2 = night_end - offset
            if start_day_2 >= end_day_2:
                start_day_2 = end_day_2 - offset
            if end_day_1 >= start_day_2:
                end_day_1 = start_day_2 - offset
            if start_day_1 >= end_day_1:
                start_day_1 = end_day_1 - offset
            if start_day_1 <= start_night:
                raise ValueError('Invalid schedule')

            schedule_data = {0: temp_night,
                             start_day_1: temp_day_1,
                             end_day_1: temp_night,
                             start_day_2: temp_day_2,
                             end_day_2: temp_night}
            schedule = DaySchedule(thermostat=thermostat, mode=mode, index=i, schedule_data=schedule_data)
            db.add(schedule)

    @classmethod
    def _migrate_pump_group(cls, db, eeprom_object):
        # type: (Session, Any) -> None
        if eeprom_object.output not in (None, 255):
            output = db.query(Output).where(Output.number == eeprom_object.output).one()
            name = 'Pump (output {0})'.format(output.number)
            pump = Pump(name=name, output=output)
            db.add(pump)
            for output_nr in (int(x) for x in eeprom_object.outputs.split(',')):
                linked_output = db.query(Output).where(Output.number == output_nr).one()
                name = 'Valve (output {0})'.format(linked_output.number)
                valve = db.query(Valve).where(output=output).one_or_none()
                if valve is None:
                    valve = Valve(output=output,
                                  name=name)
                    db.add(valve)
                pump_to_valve = PumpToValveAssociation(pump=pump, valve=valve)
                db.add(pump_to_valve)

    @classmethod
    def _migrate_thermostat_group(cls, db, thermostat_group, eeprom_object):
        # type: (Session, ThermostatGroup, Any) -> None
        temperature = Sensor.PhysicalQuantities.TEMPERATURE
        if eeprom_object.outside_sensor not in (None, 255):
            sensor = db.query(Sensor).where(
                (Sensor.physical_quantity == temperature) &
                (Sensor.external_id == str(eeprom_object.outside_sensor))
            ).one_or_none()
            if sensor is None:
                sensor = db.query(Sensor).where(
                    (Sensor.physical_quantity is None) &
                    (Sensor.external_id == str(eeprom_object.outside_sensor))
                ).one_or_none()
                if sensor is None:
                    sensor = Sensor(pysical_quantity=None,
                                    external_id=str(eeprom_object.outside_sensor))
                    db.add(sensor)
                sensor.physical_quantity = temperature
                sensor.unit = Sensor.Units.CELCIUS
            if sensor is None:
                raise ValueError('Thermostat <Sensor external_id={}> does not exist'.format(eeprom_object.outside_sensor))
            thermostat_group.sensor = sensor
        if eeprom_object.threshold_temp not in (None, 255):
            thermostat_group.threshold_temperature = eeprom_object.threshold_temp

        for mode in [ThermostatGroup.Modes.HEATING, ThermostatGroup.Modes.COOLING]:
            for i in range(4):
                output_field = 'switch_to_{0}_output_{1}'.format(mode, i)
                value_field = 'switch_to_{0}_value_{1}'.format(mode, i)
                if getattr(eeprom_object, output_field) not in (None, 255):
                    output = db.query(Output).where(Output.number == getattr(eeprom_object, output_field)).one()
                    value = 0 if getattr(eeprom_object, value_field) in (None, 255, 0) else 100
                    o2tg = OutputToThermostatGroupAssociation(thermostat_group=thermostat_group, output=output, mode=mode, value=value, index=0)
                    db.add(o2tg)

        for valve in db.query(Valve).all():
            valve.delay = eeprom_object.pump_delay

    @staticmethod
    @Inject
    def _read_global_configuration(eeprom_controller=INJECTED):
        # type: (EepromController) -> GlobalThermostatConfiguration
        return eeprom_controller.read(GlobalThermostatConfiguration)

    @staticmethod
    @Inject
    def _read_heating_configuration(eeprom_controller=INJECTED):
        # type: (EepromController) -> List[ThermostatConfiguration]
        return eeprom_controller.read_all(ThermostatConfiguration)

    @staticmethod
    @Inject
    def _read_cooling_configuration(eeprom_controller=INJECTED):
        # type: (EepromController) -> List[CoolingConfiguration]
        return eeprom_controller.read_all(CoolingConfiguration)

    @staticmethod
    @Inject
    def _read_pump_group_configuration(eeprom_controller=INJECTED):
        # type: (EepromController) -> List[PumpGroupConfiguration]
        return eeprom_controller.read_all(PumpGroupConfiguration)

    @staticmethod
    def _enumerate_schedules(thermostat_configuration):
        # type: (ThermostatConfiguration) -> Iterable[Tuple[int,Any]]
        return enumerate([thermostat_configuration.auto_mon,
                          thermostat_configuration.auto_tue,
                          thermostat_configuration.auto_wed,
                          thermostat_configuration.auto_thu,
                          thermostat_configuration.auto_fri,
                          thermostat_configuration.auto_sat,
                          thermostat_configuration.auto_sun])

    @staticmethod
    @Inject
    def _disable_master_thermostats(master_communicator=INJECTED):
        # type: (MasterCommunicator) -> None
        master_communicator.do_command(
            master_api.write_eeprom(),
            {'bank': 0, 'address': 40, 'data': bytearray([0x00])}
        )
