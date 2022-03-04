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
import time
import mock
from peewee import SqliteDatabase

from gateway.enums import ModuleType
from gateway.api.serializers import ModuleSerializer
from gateway.dto import ModuleDTO
from gateway.hal.master_controller import MasterController
from gateway.models import Module
from gateway.module_controller import ModuleController
from gateway.pubsub import PubSub
from gateway.energy_module_controller import EnergyModuleController
from ioc import SetTestMode, SetUpTestInjections
from enums import HardwareType
import fakesleep

MODELS = [Module]


class ModuleControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()
        cls.test_db = SqliteDatabase(':memory:')

    def setUp(self):
        fakesleep.monkey_patch()
        self.test_db.bind(MODELS, bind_refs=False, bind_backrefs=False)
        self.test_db.connect()
        self.test_db.create_tables(MODELS)
        self.pubsub = PubSub()
        SetUpTestInjections(pubsub=self.pubsub)
        self.master_controller = mock.Mock(MasterController)
        self.energy_module_controller=mock.Mock(EnergyModuleController)
        SetUpTestInjections(master_controller=self.master_controller,
                            maintenance_controller=mock.Mock(),
                            energy_module_controller=self.energy_module_controller)
        self.controller = ModuleController()
        module = Module.create(address=2,
                               source=ModuleDTO.Source.GATEWAY,
                               hardware_type=HardwareType.PHYSICAL,
                               module_type=ModuleType.ENERGY)
        module.save()

    def tearDown(self):
        self.test_db.drop_tables(MODELS)
        self.test_db.close()
        fakesleep.monkey_restore()

    def test_module_sync(self):
        master_modules = [ModuleDTO(id=0,
                                    source=ModuleDTO.Source.MASTER,
                                    module_type=ModuleType.OUTPUT,
                                    address='079.000.000.001',
                                    hardware_type=HardwareType.PHYSICAL,
                                    firmware_version='3.1.0',
                                    hardware_version='4',
                                    order=0,
                                    online=True,
                                    last_online_update=int(time.time()))]
        energy_modules = [ModuleDTO(id=0,
                                    source=ModuleDTO.Source.GATEWAY,
                                    module_type=ModuleType.ENERGY,
                                    address='2',
                                    hardware_type=HardwareType.PHYSICAL,
                                    firmware_version=None,
                                    hardware_version=None)]
        self.master_controller.get_modules_information.return_value = master_modules
        self.energy_module_controller.get_modules_information.return_value = []  # Empty, should not remove EM
        self.controller.run_sync_orm()
        self.assertEqual(energy_modules + master_modules, self.controller.load_modules())
        self.assertEqual([], self.controller.load_modules(address='000.000.000.000'))

    def test_module_offline(self):
        dto = ModuleDTO(id=0,
                        source=ModuleDTO.Source.MASTER,
                        module_type=ModuleType.OUTPUT,
                        address='079.000.000.001',
                        hardware_type=HardwareType.PHYSICAL,
                        firmware_version='3.1.0',
                        hardware_version='4',
                        order=0)
        self.master_controller.get_modules_information.return_value = [dto]
        self.energy_module_controller.get_modules_information.return_value = []
        self.controller.run_sync_orm()
        received_dto = self.controller.load_modules(source=ModuleDTO.Source.MASTER)[0]
        self.assertIsNone(received_dto.firmware_version)
        self.assertIsNone(received_dto.hardware_version)
        dto.online = True
        self.controller.run_sync_orm()
        received_dto = self.controller.load_modules(source=ModuleDTO.Source.MASTER)[0]
        self.assertEqual('3.1.0', received_dto.firmware_version)
        self.assertEqual('4', received_dto.hardware_version)
        dto.online = False
        self.controller.run_sync_orm()
        received_dto = self.controller.load_modules(source=ModuleDTO.Source.MASTER)[0]
        self.assertEqual('3.1.0', received_dto.firmware_version)
        self.assertEqual('4', received_dto.hardware_version)

    def test_serialization(self):
        master_module = ModuleDTO(id=0,
                                  source=ModuleDTO.Source.MASTER,
                                  module_type=ModuleType.OUTPUT,
                                  address='079.000.000.001',
                                  hardware_type=HardwareType.PHYSICAL,
                                  firmware_version='3.1.0',
                                  hardware_version='4',
                                  order=0)
        master_module_internal = ModuleDTO(id=0,
                                           source=ModuleDTO.Source.MASTER,
                                           module_type=ModuleType.OUTPUT,
                                           address='079.000.000.001',
                                           hardware_type=HardwareType.INTERNAL,
                                           firmware_version='3.1.0',
                                           hardware_version='4',
                                           order=0)
        energy_module = ModuleDTO(id=0,
                                  source=ModuleDTO.Source.GATEWAY,
                                  module_type=ModuleType.ENERGY,
                                  address='2',
                                  hardware_type=HardwareType.PHYSICAL,
                                  firmware_version='1.2.3',
                                  order=0)
        self.assertEqual({'source': 'master',
                          'module_type': 'output',
                          'firmware_version': '3.1.0',
                          'hardware_type': 'physical',
                          'order': 0,
                          'update_success': None,
                          'address': '079.000.000.001'}, ModuleSerializer.serialize(master_module, fields=None))
        self.assertEqual({'source': 'master',
                          'module_type': 'output',
                          'firmware_version': '3.1.0',
                          'hardware_type': 'internal',
                          'order': 0,
                          'update_success': None,
                          'address': '079.000.000.001'}, ModuleSerializer.serialize(master_module_internal, fields=None))
        self.assertEqual({'source': 'gateway',
                          'module_type': 'energy',
                          'firmware_version': '1.2.3',
                          'hardware_type': 'physical',
                          'order': 0,
                          'update_success': None,
                          'address': '2'}, ModuleSerializer.serialize(energy_module, fields=None))
