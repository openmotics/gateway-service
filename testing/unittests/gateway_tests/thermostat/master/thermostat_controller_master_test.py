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

from gateway.dto import ThermostatDTO
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
        SetUpTestInjections(pubsub=self.pubsub,
                            master_controller=mock.Mock(MasterClassicController),
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
            self.pubsub._publisher_loop()
            event_data = {'id': 1,
                          'status': {'preset': 'AUTO',
                                     'current_setpoint': None,
                                     'actual_temperature': None,
                                     'output_0': None,
                                     'output_1': None},
                          'location': {'room_id': 255}}
            assert GatewayEvent(GatewayEvent.Types.THERMOSTAT_CHANGE, event_data) in events

    def test_eeprom_events(self):
        master_event = MasterEvent(MasterEvent.Types.EEPROM_CHANGE, {})
        with mock.patch.object(self.controller, 'invalidate_cache') as handle_event:
            self.pubsub.publish_master_event(PubSub.MasterTopics.EEPROM, master_event)
            self.pubsub._publisher_loop()
            handle_event.assert_called()
