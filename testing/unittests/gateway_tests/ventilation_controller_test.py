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
from peewee import Select

from bus.om_bus_client import MessageClient
from gateway.dto import VentilationDTO, VentilationSourceDTO, \
    VentilationStatusDTO
from gateway.events import GatewayEvent
from gateway.models import Plugin, Ventilation
from gateway.ventilation_controller import VentilationController
from ioc import SetTestMode, SetUpTestInjections


class VentilationControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        SetUpTestInjections(message_client=mock.Mock(MessageClient))
        self.controller = VentilationController()

    def test_set_status(self):
        plugin = Plugin(id=2, name='dummy', version='0.0.1')
        with mock.patch.object(Select, 'count', return_value=1), \
             mock.patch.object(Ventilation, 'get',
                               side_effect=[Ventilation(id=42, amount_of_levels=4, source='plugin', plugin=plugin),
                                            Ventilation(id=43, amount_of_levels=4, source='plugin', plugin=plugin)]), \
             mock.patch.object(Ventilation, 'select',
                               return_value=[Ventilation(id=42, amount_of_levels=4, source='plugin', plugin=plugin),
                                             Ventilation(id=43, amount_of_levels=4, source='plugin', plugin=plugin)]):
            self.controller.set_status(VentilationStatusDTO(42, 'manual', level=0))
            self.controller.set_status(VentilationStatusDTO(43, 'manual', level=2, timer=60.0))
            status = self.controller.get_status()
            assert {'manual'} == set(x.mode for x in status)
            assert {42, 43} == set(x.id for x in status)
            assert {0, 2} == set(x.level for x in status)
            assert {None, 60.0} == set(x.timer for x in status)

    def test_set_level(self):
        plugin = Plugin(id=2, name='dummy', version='0.0.1')
        with mock.patch.object(Select, 'count', return_value=1), \
             mock.patch.object(Ventilation, 'get',
                               side_effect=[Ventilation(id=42, amount_of_levels=4, source='plugin', plugin=plugin),
                                            Ventilation(id=43, amount_of_levels=4, source='plugin', plugin=plugin)]), \
             mock.patch.object(Ventilation, 'select',
                               return_value=[Ventilation(id=42, amount_of_levels=4, source='plugin', plugin=plugin),
                                             Ventilation(id=43, amount_of_levels=4, source='plugin', plugin=plugin)]):
            self.controller.set_level(42, 0)
            self.controller.set_level(43, 2, timer=60.0)
            status = self.controller.get_status()
            assert {'manual'} == set(x.mode for x in status)
            assert {42, 43} == set(x.id for x in status)
            assert {0, 2} == set(x.level for x in status)
            assert {None, 60.0} == set(x.timer for x in status)

    def test_mode_auto(self):
        plugin = Plugin(id=2, name='dummy', version='0.0.1')
        with mock.patch.object(Select, 'count', return_value=1), \
             mock.patch.object(Ventilation, 'get',
                               side_effect=[Ventilation(id=42, amount_of_levels=4, source='plugin', plugin=plugin),
                                            Ventilation(id=43, amount_of_levels=4, source='plugin', plugin=plugin),
                                            Ventilation(id=43, amount_of_levels=4, source='plugin', plugin=plugin)]), \
             mock.patch.object(Ventilation, 'select',
                               return_value=[Ventilation(id=42, amount_of_levels=4, source='plugin', plugin=plugin),
                                             Ventilation(id=43, amount_of_levels=4, source='plugin', plugin=plugin)]):
            self.controller.set_mode_auto(42)
            self.controller.set_level(43, 2, timer=60.0)
            status = self.controller.get_status()
            assert {'auto', 'manual'} == set(x.mode for x in status)

            self.controller.set_mode_auto(43)
            status = self.controller.get_status()
            assert {'auto'} == set(x.mode for x in status)
            assert {42, 43} == set(x.id for x in status)
            assert {None} == set(x.level for x in status)
            assert {None} == set(x.timer for x in status)

    def test_set_invalid_level(self):
        plugin = Plugin(id=2, name='dummy', version='0.0.1')
        with mock.patch.object(Select, 'count', return_value=1), \
             mock.patch.object(Ventilation, 'get',
                               return_value=Ventilation(id=42, amount_of_levels=4, souurce='plugin', plugin=plugin)):
            self.assertRaises(ValueError, self.controller.set_level, 42, 5)
            self.assertRaises(ValueError, self.controller.set_level, 42, -1)

    def test_load_ventilation(self):
        with mock.patch.object(Ventilation, 'get',
                               return_value=Ventilation(id=42,
                                                        source='plugin',
                                                        external_id='device-000001',
                                                        name='foo',
                                                        amount_of_levels=4,
                                                        device_vendor='example',
                                                        device_type='model-0',
                                                        device_serial='device-000001',
                                                        plugin=Plugin(id=2,
                                                                      name='dummy',
                                                                      version='0.0.1'))):
            ventilation_dto = self.controller.load_ventilation(42)
            assert ventilation_dto == VentilationDTO(id=42,
                                                     external_id='device-000001',
                                                     source=VentilationSourceDTO(id=2,
                                                                                 name='dummy',
                                                                                 type='plugin'),
                                                     name='foo',
                                                     amount_of_levels=4,
                                                     device_vendor='example',
                                                     device_type='model-0',
                                                     device_serial='device-000001')

    def test_create_ventilation(self):
        plugin = Plugin(id=2, name='dummy', version='0.0.1')
        with mock.patch.object(Plugin, 'get',
                               return_value=plugin), \
             mock.patch.object(Ventilation, 'get_or_none', return_value=None) as get_or_none, \
             mock.patch.object(Ventilation, 'save', return_value=None) as save:
            ventilation_dto = VentilationDTO(None,
                                             external_id='device-000001',
                                             source=VentilationSourceDTO(id=2,
                                                                         name='dummy',
                                                                         type='plugin'),
                                             name='foo',
                                             amount_of_levels=4,
                                             device_vendor='example',
                                             device_type='model-0',
                                             device_serial='device-000001')
            ventilation_dto = self.controller.save_ventilation(ventilation_dto, [])
            get_or_none.assert_called_with(source='plugin', plugin=plugin, external_id='device-000001')
            save.assert_called()

    def test_update_ventilation(self):
        plugin = Plugin(id=2, name='dummy', version='0.0.1')
        with mock.patch.object(Plugin, 'get',
                               return_value=plugin), \
             mock.patch.object(Ventilation, 'get_or_none',
                               return_value=Ventilation(id=42,
                                                        source='plugin',
                                                        source_id=2,
                                                        external_id='device-000001',
                                                        name='foo',
                                                        amount_of_levels=4,
                                                        device_type='model-0',
                                                        device_vendor='example',
                                                        device_serial='device-000001',
                                                        plugin=plugin)) as get_or_none, \
             mock.patch.object(Ventilation, 'save', return_value=None) as save:
            ventilation_dto = VentilationDTO(None,
                                             external_id='device-000001',
                                             source=VentilationSourceDTO(id=2,
                                                                         name='dummy',
                                                                         type='plugin'),
                                             name='foo',
                                             amount_of_levels=4,
                                             device_vendor='example',
                                             device_type='model-0',
                                             device_serial='device-000001')
            ventilation_dto = self.controller.save_ventilation(ventilation_dto, [])
            get_or_none.assert_called_with(source='plugin', plugin=plugin, external_id='device-000001')
            save.assert_called()

    def test_update_existing_ventilation(self):
        plugin = Plugin(id=2, name='dummy', version='0.0.1')
        with mock.patch.object(Plugin, 'get', return_value=plugin), \
             mock.patch.object(Ventilation, 'get_or_none',
                               return_value=Ventilation(id=42,
                                                        source='plugin',
                                                        source_id=2,
                                                        external_id='device-000001',
                                                        name='foo',
                                                        amount_of_levels=4,
                                                        device_type='model-0',
                                                        device_vendor='example',
                                                        device_serial='device-000001',
                                                        plugin=plugin)) as get_or_none, \
             mock.patch.object(Ventilation, 'save', return_value=None) as save:
            ventilation_dto = VentilationDTO(id=42,
                                             external_id='device-000001',
                                             source=VentilationSourceDTO(id=2,
                                                                         name='dummy',
                                                                         type='plugin'),
                                             name='foo',
                                             amount_of_levels=4,
                                             device_vendor='example',
                                             device_type='model-0',
                                             device_serial='device-000001')
            ventilation_dto = self.controller.save_ventilation(ventilation_dto, [])
            get_or_none.assert_called_with(id=42, source='plugin', plugin=plugin, external_id='device-000001')
            save.assert_called()

    def test_ventilation_change_events(self):
        plugin = Plugin(id=2, name='dummy', version='0.0.1')
        def get_ventilation(id):
            return Ventilation(id=id, amount_of_levels=4, source='plugin', plugin=plugin)
        with mock.patch.object(Select, 'count', return_value=1), \
             mock.patch.object(Ventilation, 'get', side_effect=get_ventilation), \
             mock.patch.object(Ventilation, 'select',
                               return_value=[get_ventilation(42), get_ventilation(43)]):
            self.controller.set_status(VentilationStatusDTO(42, 'manual', level=0))
            self.controller.set_status(VentilationStatusDTO(43, 'manual', level=2, timer=60.0))

            events = []

            def callback(event):
                events.append(event)
            self.controller.subscribe_events(callback)

            self.controller.set_status(VentilationStatusDTO(42, 'manual', level=0))
            self.controller.set_status(VentilationStatusDTO(43, 'manual', level=2, timer=60.0))
            assert GatewayEvent(GatewayEvent.Types.VENTILATION_CHANGE,
                                {'id': 43, 'mode': 'manual', 'level': 2, 'timer': 60.0}) in events
            assert len(events) == 1, events
