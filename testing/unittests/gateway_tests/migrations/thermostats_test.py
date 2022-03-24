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
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from gateway.models import Base, Database, ThermostatGroup, Sensor, Output, \
    Thermostat, Valve, ValveToThermostatAssociation, NoResultFound, \
    Preset, DaySchedule, Pump
from gateway.migrations.thermostats import ThermostatsMigrator, \
    GlobalThermostatConfiguration, ThermostatConfiguration, CoolingConfiguration, PumpGroupConfiguration
from ioc import SetTestMode


class ThermostatMigratorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        engine = create_engine(
            'sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool
        )
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(autocommit=False, autoflush=True, bind=engine)

        self.session = session_factory()
        session_mock = mock.patch.object(Database, 'get_session', return_value=self.session)
        session_mock.start()
        self.addCleanup(session_mock.stop)

    @mock.patch.object(ThermostatsMigrator, '_read_global_configuration')
    @mock.patch.object(ThermostatsMigrator, '_read_heating_configuration')
    @mock.patch.object(ThermostatsMigrator, '_read_cooling_configuration')
    @mock.patch.object(ThermostatsMigrator, '_read_pump_group_configuration')
    @mock.patch.object(ThermostatsMigrator, '_disable_master_thermostats')
    def test_migration(self, dmt, rpgc, rcc, rhc, rgc):
        gc_data = {'outside_sensor': 1,
                   'threshold_temp': 37,
                   'pump_delay': 15}
        for mode in [ThermostatGroup.Modes.HEATING, ThermostatGroup.Modes.COOLING]:
            for i in range(4):
                output_key = 'switch_to_{0}_output_{1}'.format(mode, i)
                value_key = 'switch_to_{0}_value_{1}'.format(mode, i)
                if i == 0:
                    gc_data[output_key] = 10 if mode == ThermostatGroup.Modes.HEATING else 11
                    gc_data[value_key] = 33
                else:
                    gc_data[output_key] = 255
                    gc_data[value_key] = 255
        gc = GlobalThermostatConfiguration.from_dict(gc_data)
        rgc.return_value = gc
        rhc.return_value = [
            ThermostatConfiguration.from_dict({'id': 0,
                                               'name': 'Heating 0',
                                               'setp0': 14.0, 'setp1': 15.0, 'setp2': 16.0, 'setp3': 17.0, 'setp4': 18.0, 'setp5': 19.0,
                                               'sensor': 2,
                                               'output0': 5, 'output1': 255,
                                               'pid_p': 1, 'pid_i': 2, 'pid_d': 3, 'pid_int': 4,
                                               'permanent_manual': 255,
                                               'auto_mon': [19.0, '07:00', '09:00', 20.0, '17:00', '22:00', 21.0],
                                               'auto_tue': [19.0, '07:00', '09:00', 20.0, '17:00', '22:00', 21.0],
                                               'auto_wed': [19.0, '07:00', '09:00', 20.0, '12:30', '22:00', 21.0],
                                               'auto_thu': [19.0, '07:00', '09:00', 20.0, '17:00', '22:00', 21.0],
                                               'auto_fri': [19.0, '07:00', '09:00', 20.0, '17:00', '22:00', 21.0],
                                               'auto_sat': [19.0, '07:00', '18:00', 20.0, '18:00', '22:00', 21.0],
                                               'auto_sun': [19.0, '07:00', '18:00', 20.0, '18:00', '22:00', 21.0]}),
            ThermostatConfiguration.from_dict({'id': 1,
                                               'name': 'Heating 1',
                                               'setp0': 14.5, 'setp1': 15.5, 'setp2': 16.5, 'setp3': 17.5,
                                               'setp4': 18.5, 'setp5': 19.5,
                                               'sensor': 3,
                                               'output0': 6, 'output1': 7,
                                               'pid_p': 5, 'pid_i': 6, 'pid_d': 7, 'pid_int': 8,
                                               'permanent_manual': 255,
                                               'auto_mon': [19.5, '07:10', '09:00', 20.5, '17:00', '22:00', 21.5],
                                               'auto_tue': [19.5, '07:10', '09:00', 20.5, '17:00', '22:00', 21.5],
                                               'auto_wed': [19.5, '07:10', '09:00', 20.5, '12:30', '22:00', 21.5],
                                               'auto_thu': [19.5, '07:10', '09:00', 20.5, '17:00', '22:00', 21.5],
                                               'auto_fri': [19.5, '07:10', '09:00', 20.5, '17:00', '22:00', 21.5],
                                               'auto_sat': [19.5, '07:10', '18:00', 20.5, '18:00', '22:00', 21.5],
                                               'auto_sun': [19.5, '07:10', '18:00', 20.5, '18:00', '22:00', 21.5]})
        ]
        rcc.return_value = [
            CoolingConfiguration.from_dict({'id': 0,
                                            'name': 'Cooling 0',
                                            'setp0': 24.0, 'setp1': 25.0, 'setp2': 26.0, 'setp3': 27.0, 'setp4': 28.0, 'setp5': 29.0,
                                            'sensor': 4,  # This sensor will be ignored due to architecture
                                            'output0': 6, 'output1': 255,
                                            'pid_p': 10, 'pid_i': 20, 'pid_d': 30, 'pid_int': 40,
                                            'permanent_manual': 255,
                                            'auto_mon': [29.0, '07:20', '09:00', 30.0, '17:00', '22:00', 31.0],
                                            'auto_tue': [29.0, '07:20', '09:00', 30.0, '17:00', '22:00', 31.0],
                                            'auto_wed': [29.0, '07:20', '09:00', 30.0, '12:30', '22:00', 31.0],
                                            'auto_thu': [29.0, '07:20', '09:00', 30.0, '17:00', '22:00', 31.0],
                                            'auto_fri': [29.0, '07:20', '09:00', 30.0, '17:00', '22:00', 31.0],
                                            'auto_sat': [29.0, '07:20', '18:00', 30.0, '18:00', '22:00', 31.0],
                                            'auto_sun': [29.0, '07:20', '18:00', 30.0, '18:00', '22:00', 31.0]})
        ]
        rpgc.return_value = [
            PumpGroupConfiguration.from_dict({'id': 0,
                                              'output': 8,
                                              'outputs': '5,6,7'})
        ]

        with self.session as db:
            sensor_1 = Sensor(external_id='1',
                              physical_quantity=Sensor.PhysicalQuantities.TEMPERATURE,
                              source=Sensor.Sources.MASTER,
                              name='Sensor 1')
            sensor_2 = Sensor(external_id='2',
                              physical_quantity=Sensor.PhysicalQuantities.TEMPERATURE,
                              source=Sensor.Sources.MASTER,
                              name='Sensor 2')
            sensor_3 = Sensor(external_id='3',
                              physical_quantity=Sensor.PhysicalQuantities.TEMPERATURE,
                              source=Sensor.Sources.MASTER,
                              name='Sensor 3')
            sensor_4 = Sensor(external_id='4',
                              physical_quantity=Sensor.PhysicalQuantities.TEMPERATURE,
                              source=Sensor.Sources.MASTER,
                              name='Sensor 4')
            output_5 = Output(number=5)
            output_6 = Output(number=6)
            output_7 = Output(number=7)
            output_8 = Output(number=8)
            output_10 = Output(number=10)
            output_11 = Output(number=11)
            objects = [sensor_1, sensor_2, sensor_3, sensor_4,
                       output_5, output_6, output_7, output_8, output_10, output_11]
            db.add_all(objects)
            db.commit()
            for o in objects:
                db.refresh(o)

            with self.assertRaises(NoResultFound):
                ThermostatsMigrator._migrate()

            db.add(ThermostatGroup(number=0,
                                   name='Default group'))
            db.commit()

            ThermostatsMigrator._migrate()

            dmt.assert_called_once()

            thermostat_groups = db.query(ThermostatGroup).all()
            self.assertEqual(1, len(thermostat_groups))
            thermostat_group = thermostat_groups[0]  # type: ThermostatGroup
            self.assertEqual('Default group', thermostat_group.name)
            thermostats = db.query(Thermostat).all()
            self.assertEqual(2, len(thermostats))
            thermostat_0 = thermostats[0]  # type: Thermostat
            expected_thermostat_0 = {'id': thermostat_0.id, 'number': 0,
                                     'thermostat_group_id': thermostat_group.id,
                                     'name': 'Heating 0',
                                     'sensor_id': sensor_2.id,
                                     'pid_heating_p': 1.0, 'pid_heating_i': 2.0, 'pid_heating_d': 3.0,
                                     'pid_cooling_p': 10.0, 'pid_cooling_i': 20.0, 'pid_cooling_d': 30.0,
                                     'valve_config': 'cascade',
                                     'state': 'on', 'automatic': True,
                                     'room_id': None}
            self.assertEqual(expected_thermostat_0,
                             ThermostatMigratorTest._extract_dict(thermostat_0,
                                                                  expected_thermostat_0.keys()))
            heating_valve = db.query(Valve).join(ValveToThermostatAssociation).where((ValveToThermostatAssociation.thermostat == thermostat_0) &
                                                                                     (ValveToThermostatAssociation.mode == 'heating')).one()  # type: Valve
            self.assertEqual([{'priority': 0, 'thermostat_id': thermostat_0.id, 'mode': 'heating', 'valve_id': heating_valve.id}],
                             [ThermostatMigratorTest._extract_dict(x) for x in thermostat_0.heating_valve_associations])
            self.assertEqual(output_5.id, heating_valve.output_id)
            cooling_valve = db.query(Valve).join(ValveToThermostatAssociation).where((ValveToThermostatAssociation.thermostat == thermostat_0) &
                                                                                     (ValveToThermostatAssociation.mode == 'cooling')).one()  # type: Valve
            self.assertEqual([{'priority': 0, 'thermostat_id': thermostat_0.id, 'mode': 'cooling', 'valve_id': cooling_valve.id}],
                             [ThermostatMigratorTest._extract_dict(x) for x in thermostat_0.cooling_valve_associations])
            self.assertEqual(output_6.id, cooling_valve.output_id)
            self.assertEqual(sensor_2.id, thermostat_0.sensor.id)

            thermostat_1 = thermostats[1]  # type: Thermostat
            expected_thermostat_1 = {'id': thermostat_1.id, 'number': 1,
                                     'thermostat_group_id': thermostat_group.id,
                                     'name': 'Heating 1',
                                     'sensor_id': sensor_3.id,
                                     'pid_heating_p': 5.0, 'pid_heating_i': 6.0, 'pid_heating_d': 7.0,
                                     'pid_cooling_p': 120.0, 'pid_cooling_i': 0.0, 'pid_cooling_d': 0.0,
                                     'valve_config': 'cascade',
                                     'state': 'on', 'automatic': True,
                                     'room_id': None}
            self.assertEqual(expected_thermostat_1,
                             ThermostatMigratorTest._extract_dict(thermostat_1,
                                                                  expected_thermostat_1.keys()))
            heating_valves = db.query(Valve).join(ValveToThermostatAssociation).where((ValveToThermostatAssociation.thermostat == thermostat_1) &
                                                                                      (ValveToThermostatAssociation.mode == 'heating'))
            self.assertEqual([{'priority': heating_valve.thermostat_associations[0].priority, 'thermostat_id': thermostat_1.id,
                               'mode': 'heating', 'valve_id': heating_valve.id}
                              for heating_valve in heating_valves],
                             [ThermostatMigratorTest._extract_dict(x) for x in thermostat_1.heating_valve_associations])
            self.assertEqual(sorted([output_6.id, output_7.id]), sorted(v.output_id for v in heating_valves))
            cooling_valve = db.query(Valve).join(ValveToThermostatAssociation).where((ValveToThermostatAssociation.thermostat == thermostat_1) &
                                                                                     (ValveToThermostatAssociation.mode == 'cooling')).first()
            self.assertIsNone(cooling_valve)
            self.assertEqual(sensor_3.id, thermostat_1.sensor.id)

            presets = db.query(Preset).where(Preset.thermostat == thermostat_0).all()
            preset_map = {p.type: p for p in presets}
            self.assertEqual(17.0, preset_map['away'].heating_setpoint)
            self.assertEqual(27.0, preset_map['away'].cooling_setpoint)
            self.assertEqual(18.0, preset_map['vacation'].heating_setpoint)
            self.assertEqual(28.0, preset_map['vacation'].cooling_setpoint)
            self.assertEqual(19.0, preset_map['party'].heating_setpoint)
            self.assertEqual(29.0, preset_map['party'].cooling_setpoint)

            schedules = db.query(DaySchedule).where(DaySchedule.thermostat == thermostat_0).all()
            possible_schedules = [s for s in schedules if s.mode == 'heating' and s.index == 0]
            self.assertEqual(1, len(possible_schedules))
            self.assertEqual({0: 19.0,
                              7 * 60 * 60: 20.0,
                              9 * 60 * 60: 19.0,
                              17 * 60 * 60: 21.0,
                              22 * 60 * 60: 19.0},  # 'auto_mon': [19.0, '07:00', '09:00', 20.0, '17:00', '22:00', 21.0]
                             possible_schedules[0].schedule_data)
            possible_schedules = [s for s in schedules if s.mode == 'heating' and s.index == 5]
            self.assertEqual(1, len(possible_schedules))
            self.assertEqual({0: 19.0,
                              7 * 60 * 60: 20.0,
                              18 * 60 * 60: 19.0,
                              18 * 60 * 60 + 600: 21.0,
                              22 * 60 * 60: 19.0},  # 'auto_sat': [19.0, '07:00', '18:00', 20.0, '18:00', '22:00', 21.0]
                             possible_schedules[0].schedule_data)
            possible_schedules = [s for s in schedules if s.mode == 'cooling' and s.index == 0]
            self.assertEqual(1, len(possible_schedules))
            self.assertEqual({0: 29.0,
                              7 * 60 * 60 + 20 * 60: 30.0,
                              9 * 60 * 60: 29.0,
                              17 * 60 * 60: 31.0,
                              22 * 60 * 60: 29.0},  # 'auto_mon': [29.0, '07:20', '09:00', 30.0, '17:00', '22:00', 31.0]
                             possible_schedules[0].schedule_data)

            pump = db.query(Pump).one()
            self.assertEqual(output_8.id, pump.output.id)
            self.assertEqual(sorted([output_5.id, output_6.id, output_7.id]), sorted(v.output.id for v in pump.valves))

    @staticmethod
    def _extract_dict(orm_entity, fields=None):
        return {c.name: getattr(orm_entity, c.name)
                for c in orm_entity.__table__.columns
                if fields is None or c.name in fields}
