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
from __future__ import absolute_import

import unittest

import mock

from gateway.dto import ThermostatDTO, ThermostatScheduleDTO
from gateway.events import GatewayEvent
from gateway.hal.master_controller_classic import MasterClassicController
from gateway.hal.master_event import MasterEvent
from gateway.output_controller import OutputController
from gateway.pubsub import PubSub
from gateway.thermostat.master.thermostat_controller_master import \
    ThermostatControllerMaster
from ioc import SetTestMode, SetUpTestInjections


class ThermostatControllerMasterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.pubsub = PubSub()
        self._master_controller = mock.Mock(MasterClassicController)
        SetUpTestInjections(pubsub=self.pubsub,
                            master_controller=self._master_controller,
                            output_controller=mock.Mock(OutputController))
        self.controller = ThermostatControllerMaster()

    def test_thermostat_change_events(self):
        events = []

        def handle_event(gateway_event):
            events.append(gateway_event)

        self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.STATE, handle_event)

        with mock.patch.object(self.controller, 'invalidate_cache') as handle_event:
            status = {'act': None,
                      'csetp': None,
                      'setpoint': None,
                      'output0': None,
                      'output1': None}
            self.controller._thermostats_config = {1: ThermostatDTO(1)}
            self.controller._thermostat_status._report_change(1, status)
            self.pubsub._publish_all_events(blocking=False)
            event_data = {'id': 1,
                          'status': {'preset': 'AUTO',
                                     'current_setpoint': None,
                                     'actual_temperature': None,
                                     'output_0': None,
                                     'output_1': None},
                          'location': {'room_id': 255}}
            assert GatewayEvent(GatewayEvent.Types.THERMOSTAT_CHANGE, event_data) in events

    def test_eeprom_events(self):
        master_event = MasterEvent(MasterEvent.Types.CONFIGURATION_CHANGE, {})
        with mock.patch.object(self.controller, 'invalidate_cache') as handle_event:
            self.pubsub.publish_master_event(PubSub.MasterTopics.CONFIGURATION, master_event)
            self.pubsub._publish_all_events(blocking=False)
            handle_event.assert_called()

    def test_saving_reading_sane_values(self):
        for mode in ['heating', 'cooling']:
            for day in ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']:
                thermostat_dto = ThermostatControllerMasterTest._build_thermostat_dto(5, defaults=False, mode=mode)  # Empty timings
                self.assertEqual(None, getattr(thermostat_dto, 'auto_{0}'.format(day)))  # Validate internal `_build_thermostat_dto` method
                changed = self.controller._patch_thermostat(thermostat_dto, mode=mode)
                self.assertTrue(changed)
                expected_dto = ThermostatControllerMasterTest._build_thermostat_dto(5, defaults=True, mode=mode)
                self.assertEqual(20.0 if mode == 'heating' else 24.0,
                                 getattr(thermostat_dto, 'auto_{0}'.format(day)).temp_day_1)  # Validate internal `_build_thermostat_dto` method
                self.assertEqual(expected_dto, thermostat_dto)
                getattr(thermostat_dto, 'auto_{0}'.format(day)).temp_day_1 = None  # Set single value invalid
                changed = self.controller._patch_thermostat(thermostat_dto, mode=mode)
                self.assertTrue(changed)
                self.assertEqual(expected_dto, thermostat_dto)  # Must be restored
                changed = self.controller._patch_thermostat(thermostat_dto, mode=mode)
                self.assertFalse(changed)  # Not changed
                self.assertEqual(expected_dto, thermostat_dto)  # No change

    def test_call_patch(self):
        for mode in ['heating', 'cooling']:
            dto1 = ThermostatControllerMasterTest._build_thermostat_dto(5, defaults=False, mode=mode)
            dto2 = ThermostatControllerMasterTest._build_thermostat_dto(6, defaults=False, mode=mode)
            dto3 = ThermostatControllerMasterTest._build_thermostat_dto(7, defaults=True, mode=mode)
            with mock.patch.object(ThermostatControllerMaster, '_patch_thermostat') as patch:
                patch.side_effect = [True, True, False]
                getattr(self.controller, 'save_{0}_thermostats'.format(mode))([dto1, dto2, dto3])
                patch.assert_has_calls([mock.call(mode=mode, ref_thermostat=dto1)])
                patch.assert_has_calls([mock.call(mode=mode, ref_thermostat=dto2)])
                patch.assert_has_calls([mock.call(mode=mode, ref_thermostat=dto3)])
            dto1 = ThermostatControllerMasterTest._build_thermostat_dto(5, defaults=False, mode=mode)
            with mock.patch.object(self._master_controller, 'load_{0}_thermostat'.format(mode), return_value=dto1), \
                    mock.patch.object(self.controller, 'save_{0}_thermostats'.format(mode)) as save, \
                    mock.patch.object(ThermostatControllerMaster, '_patch_thermostat') as patch:
                patch.side_effect = [True]
                getattr(self.controller, 'load_{0}_thermostat'.format(mode))(1)
                save.assert_called_once_with([dto1])
                patch.assert_has_calls([mock.call(mode=mode, ref_thermostat=dto1)])
            dto1 = ThermostatControllerMasterTest._build_thermostat_dto(5, defaults=False, mode=mode)
            dto2 = ThermostatControllerMasterTest._build_thermostat_dto(6, defaults=False, mode=mode)
            dto3 = ThermostatControllerMasterTest._build_thermostat_dto(7, defaults=True, mode=mode)
            with mock.patch.object(self._master_controller, 'load_{0}_thermostats'.format(mode), return_value=[dto1, dto2, dto3]), \
                    mock.patch.object(self.controller, 'save_{0}_thermostats'.format(mode)) as save, \
                    mock.patch.object(ThermostatControllerMaster, '_patch_thermostat') as patch:
                patch.side_effect = [True, True, False]
                getattr(self.controller, 'load_{0}_thermostats'.format(mode))()
                save.assert_called_once_with([dto1, dto2])
                patch.assert_has_calls([mock.call(mode=mode, ref_thermostat=dto1)])
                patch.assert_has_calls([mock.call(mode=mode, ref_thermostat=dto2)])
                patch.assert_has_calls([mock.call(mode=mode, ref_thermostat=dto3)])

    @staticmethod
    def _build_thermostat_dto(id, defaults=True, mode='heating'):
        kwargs = {'auto_mon': None, 'auto_tue': None, 'auto_wed': None, 'auto_thu': None, 'auto_fri': None,
                  'auto_sat': None, 'auto_sun': None}
        if defaults:
            for day in ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']:
                times = ThermostatControllerMaster.DEFAULT_TIMINGS
                if mode == 'heating':
                    temps = ThermostatControllerMaster.DEFAULT_TEMPS_HEATING
                else:
                    temps = ThermostatControllerMaster.DEFAULT_TEMPS_COOLING
                kwargs['auto_{0}'.format(day)] = ThermostatScheduleDTO(temp_day_1=temps[0], temp_day_2=temps[1], temp_night=temps[2],
                                                                       start_day_1=times[0], end_day_1=times[1],
                                                                       start_day_2=times[2], end_day_2=times[3])
        return ThermostatDTO(id=id, name='test', permanent_manual=False,
                             setp0=0.0, setp1=1.0, setp2=2.0, setp3=3.0, setp4=4.0, setp5=5.0,
                             sensor=240, output0=0, output1=1, pid_p=10.0, pid_i=20.0, pid_d=30.0, pid_int=40.0,
                             room=None, **kwargs)
