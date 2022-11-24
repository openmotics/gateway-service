# Copyright (C) 2021 OpenMotics BV
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
from __future__ import absolute_import

import unittest

import mock
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool

from gateway.dto import PumpGroupDTO, SensorStatusDTO, ThermostatDTO, \
    ThermostatScheduleDTO
from gateway.hal.mappers_classic import PumpGroupMapper
from gateway.mappers.thermostat import ThermostatMapper, \
    ThermostatScheduleMapper
from gateway.models import Base, Database, DaySchedule, Feature, Output, \
    HvacOutputLink, Preset, Pump, PumpToValveAssociation, \
    Room, Sensor, Thermostat, ThermostatGroup, Valve, \
    IndoorLinkValves
    
from ioc import SetTestMode, SetUpTestInjections
from logs import Logs
from master.classic.eeprom_models import PumpGroupConfiguration


class ThermostatMapperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        engine = create_engine(
            'sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool
        )
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        self.session = session_factory()
        session_mock = mock.patch.object(Database, 'get_session', return_value=self.session)
        session_mock.start()
        self.addCleanup(session_mock.stop)

    def test_thermostat(self):
        with self.session as db:
            db.add_all([
                Sensor(id=510, source='master', external_id='8', physical_quantity='temperature', unit='celcius', name='sensor'),
                ThermostatGroup(id=2, number=1, name='group')
            ])
            db.commit()

        thermostat_dto = ThermostatDTO(number=0, name='thermostat', sensor=510)
        with self.session as db:
            thermostat = ThermostatMapper(db).dto_to_orm(thermostat_dto)
            assert thermostat.id is None
            assert thermostat.number == 0
            assert thermostat.name == 'thermostat'
            assert thermostat.room is None
            assert thermostat.sensor.name == 'sensor'
            assert thermostat.group.name == 'group'
            db.add(thermostat)
            db.commit()

        with self.session as db:
            thermostat = ThermostatMapper(db).dto_to_orm(thermostat_dto)
            db.add(thermostat)
            db.commit()

        with self.session as db:
            query = db.query(Thermostat)
            assert query.count() == 1, query.all()

    def test_valve_to_thermostats(self):
        with self.session as db:
            db.add_all([
                Sensor(id=510, source='master', external_id='8', physical_quantity='temperature', unit='celcius', name='sensor'),
                Output(number=8),
                Output(number=9),
                ThermostatGroup(id=2, number=1, name='group'),
                Thermostat(number=0, name='thermostat', start=0, thermostat_group_id=2),
                Valve(name='Valve (output 8)', output_id=1),
                IndoorLinkValves(valve_id=1, thermostat_link_id=1)
            ])
            db.commit()

        thermostat_dto = ThermostatDTO(number=0, output0=8, output1=9)
        with self.session as db:
            update, _ = ThermostatMapper(db).get_valve_links(thermostat_dto, 'heating')
            assert [x.valve.name for x in update] == ['Valve (output 9)']
            db.add_all(update)
            db.commit()

        with self.session as db:
            thermostat = db.get(Thermostat, 1)
            assert thermostat.number == 0
            self.assertEqual(len(thermostat.valves),2)
            self.assertTrue([x.name for x in thermostat.valves] == ['Valve (output 8)', 'Valve (output 9)'])

        with self.session as db:
            update, remove = ThermostatMapper(db).get_valve_links(thermostat_dto, 'heating')
            assert [x.valve.name for x in update] == []  # no changes
            assert [x.valve.name for x in remove] == []

        thermostat_dto = ThermostatDTO(number=0, output0=8)
        with self.session as db:
            update, remove = ThermostatMapper(db).get_valve_links(thermostat_dto, 'heating')
            assert [x.valve.name for x in update] == []
            assert len(remove) == 1

    def test_day_schedules(self):
        with self.session as db:
            db.add_all([
                Sensor(id=510, source='master', external_id='8', physical_quantity='temperature', unit='celcius', name='sensor'),
                Output(number=8),
                Output(number=9),
                ThermostatGroup(id=0, number=1, name='group'),
                Thermostat(number=10, name='thermostat', start=0, thermostat_group_id=0)
            ])
            db.commit()

        schedule_dto = ThermostatScheduleDTO(temp_day_1=21.0,
                                             start_day_1='06:00',
                                             end_day_1='08:00',
                                             temp_day_2=21.0,
                                             start_day_2='16:00',
                                             end_day_2='22:00',
                                             temp_night=19.0)
        thermostat_dto = ThermostatDTO(number=10, auto_mon=schedule_dto)
        with self.session as db:
            update, remove = ThermostatMapper(db).get_schedule_links(thermostat_dto, 'heating')
            assert [x.index for x in update] == [0]
            assert [x.schedule_data for x in update] == [{0: 19.0, 21600: 21.0, 28800: 19.0, 57600: 21.0, 79200: 19.0}]
            db.commit()

        with self.session as db:
            update, remove = ThermostatMapper(db).get_schedule_links(thermostat_dto, 'heating')
            assert [x.schedule_data for x in update] == []  # no changes

        schedule_dto = ThermostatScheduleDTO(temp_day_1=22.0,
                                             start_day_1='06:00',
                                             end_day_1='08:00',
                                             temp_day_2=22.0,
                                             start_day_2='16:00',
                                             end_day_2='22:00',
                                             temp_night=19.0)
        thermostat_dto = ThermostatDTO(number=10, auto_mon=schedule_dto)
        with self.session as db:
            update, remove = ThermostatMapper(db).get_schedule_links(thermostat_dto, 'heating')
            assert [x.schedule_data for x in update] == [{0: 19.0, 21600: 22.0, 28800: 19.0, 57600: 22.0, 79200: 19.0}]

        thermostat_dto = ThermostatDTO(number=10, auto_mon=None)
        with self.session as db:
            update, remove = ThermostatMapper(db).get_schedule_links(thermostat_dto, 'heating')
            assert update == [], [x.schedule_data for x in update]

    def test_presets(self):
        with self.session as db:
            db.add_all([
                Sensor(id=510, source='master', external_id='8', physical_quantity='temperature', unit='celcius', name='sensor'),
                Output(number=8),
                Output(number=9),
                ThermostatGroup(id=0, number=1, name='group'),
                Thermostat(number=10, name='thermostat', start=0, thermostat_group_id=0)
            ])
            db.commit()

        thermostat_dto = ThermostatDTO(number=10, setp5=32.0)
        with self.session as db:
            update, remove = ThermostatMapper(db).get_preset_links(thermostat_dto, 'heating')
            assert [x.heating_setpoint for x in update] == [32.0]
            db.commit()

        thermostat_dto = ThermostatDTO(number=10)
        with self.session as db:
            update, remove = ThermostatMapper(db).get_preset_links(thermostat_dto, 'heating')
            assert update == []  # no changes
            assert remove == []  # no changes


class ThermostatScheduleMapperTest(unittest.TestCase):
    def test_simple_schedule(self):
        schedule_dto = ThermostatScheduleDTO(temp_night=10.0,
                                             temp_day_1=26.0,
                                             start_day_1='07:00',
                                             end_day_1='09:00',
                                             temp_day_2=25.0,
                                             start_day_2='17:00',
                                             end_day_2='22:00')
        data = ThermostatScheduleMapper.dto_to_schedule(schedule_dto)
        expected_data = {0: 10.0, 25200: 26.0, 32400: 10.0, 61200: 25.0, 79200: 10.0}
        self.assertEqual(data, expected_data)
        schedule_dto = ThermostatScheduleMapper.schedule_to_dto(data, 'heating')
        self.assertEqual(schedule_dto.temp_night, 10.0)
        self.assertEqual(schedule_dto.temp_day_1, 26.0)
        self.assertEqual(schedule_dto.start_day_1, '07:00')
        self.assertEqual(schedule_dto.end_day_1, '09:00')
        self.assertEqual(schedule_dto.temp_day_2, 25.0)
        self.assertEqual(schedule_dto.start_day_2, '17:00')
        self.assertEqual(schedule_dto.end_day_2, '22:00')

    def test_from_overlapping_schedule(self):
        schedule_dto = ThermostatScheduleDTO(temp_night=10.0,
                                             temp_day_1=26.0,
                                             start_day_1='00:00',
                                             end_day_1='12:00',
                                             temp_day_2=25.0,
                                             start_day_2='12:00',
                                             end_day_2='24:00')
        data = ThermostatScheduleMapper.dto_to_schedule(schedule_dto)
        expected_data = {0: 10.0, 600: 26.0, 43200: 10.0, 43800: 25.0, 85800: 10.0}
        self.assertEqual(len(data), 5)
        self.assertEqual(data, expected_data)
        schedule_dto = ThermostatScheduleMapper.schedule_to_dto(data, 'heating')
        self.assertEqual(schedule_dto.temp_night, 10.0)
        self.assertEqual(schedule_dto.temp_day_1, 26.0)
        self.assertEqual(schedule_dto.start_day_1, '00:10')
        self.assertEqual(schedule_dto.end_day_1, '12:00')
        self.assertEqual(schedule_dto.temp_day_2, 25.0)
        self.assertEqual(schedule_dto.start_day_2, '12:10')
        self.assertEqual(schedule_dto.end_day_2, '23:50')

    def test_to_partial_schedule(self):
        data = {'0': 10.0, '21600': 26.0}
        schedule_dto = ThermostatScheduleMapper.schedule_to_dto(data, 'heating')
        self.assertEqual(schedule_dto.temp_night, 19.0)
        self.assertEqual(schedule_dto.temp_day_1, 21.0)
        self.assertEqual(schedule_dto.start_day_1, '06:00')
        self.assertEqual(schedule_dto.end_day_1, '08:00')
        self.assertEqual(schedule_dto.temp_day_2, 21.0)
        self.assertEqual(schedule_dto.start_day_2, '16:00')
        self.assertEqual(schedule_dto.end_day_2, '22:00')

    def test_to_invalid_schedule(self):
        data = {'0': 10.0, '25200': 26.0, '32400': 11.0, '61200': 25.0, '79200': 12.0}
        schedule_dto = ThermostatScheduleMapper.schedule_to_dto(data, 'heating')
        self.assertEqual(schedule_dto.temp_night, 19.0)
        self.assertEqual(schedule_dto.temp_day_1, 21.0)
        self.assertEqual(schedule_dto.start_day_1, '06:00')
        self.assertEqual(schedule_dto.end_day_1, '08:00')
        self.assertEqual(schedule_dto.temp_day_2, 21.0)
        self.assertEqual(schedule_dto.start_day_2, '16:00')
        self.assertEqual(schedule_dto.end_day_2, '22:00')



class ThermostatClassicMapperTest(unittest.TestCase):
    def test_pump_group(self):
        raw = {'id': 0, 'outputs': '', 'output': 255, 'room': 255}
        orm = PumpGroupConfiguration.deserialize(raw)
        dto = PumpGroupMapper.orm_to_dto(orm)
        self.assertEqual(PumpGroupDTO(id=0, valve_output_ids=[], pump_output_id=None, room_id=None), dto)
        self.assertEqual(raw, PumpGroupMapper.dto_to_orm(PumpGroupConfiguration, dto).serialize())

        raw = {'id': 0, 'outputs': '10', 'output': 255, 'room': 255}
        orm = PumpGroupConfiguration.deserialize(raw)
        dto = PumpGroupMapper.orm_to_dto(orm)
        self.assertEqual(PumpGroupDTO(id=0, valve_output_ids=[10], pump_output_id=None, room_id=None), dto)
        self.assertEqual(raw, PumpGroupMapper.dto_to_orm(PumpGroupConfiguration, dto).serialize())

        raw = {'id': 0, 'outputs': '10,15', 'output': 255, 'room': 255}
        orm = PumpGroupConfiguration.deserialize(raw)
        dto = PumpGroupMapper.orm_to_dto(orm)
        self.assertEqual(PumpGroupDTO(id=0, valve_output_ids=[10, 15], pump_output_id=None, room_id=None), dto)
        self.assertEqual(raw, PumpGroupMapper.dto_to_orm(PumpGroupConfiguration, dto).serialize())

        raw = {'id': 0, 'outputs': '', 'output': 15, 'room': 10}
        orm = PumpGroupConfiguration.deserialize(raw)
        dto = PumpGroupMapper.orm_to_dto(orm)
        self.assertEqual(PumpGroupDTO(id=0, valve_output_ids=[], pump_output_id=15, room_id=10), dto)
        self.assertEqual(raw, PumpGroupMapper.dto_to_orm(PumpGroupConfiguration, dto).serialize())
