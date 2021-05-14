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
"""
System configuration tests
"""
from __future__ import absolute_import
import unittest

from peewee import SqliteDatabase

from gateway.dto import SystemDoorbellConfigDTO, SystemRFIDConfigDTO, SystemRFIDSectorBlockConfigDTO, \
    SystemTouchscreenConfigDTO, SystemGlobalConfigDTO, SystemActivateUserConfigDTO
from gateway.models import Delivery, User, Config
from gateway.system_config_controller import SystemConfigController
from ioc import SetTestMode

MODELS = [Config]


class SystemConfigControllerTest(unittest.TestCase):
    """ Tests for DeliveryController. """

    @classmethod
    def setUpClass(cls):
        super(SystemConfigControllerTest, cls).setUpClass()
        SetTestMode()
        cls.test_db = SqliteDatabase(':memory:')

    @classmethod
    def tearDownClass(cls):
        super(SystemConfigControllerTest, cls).tearDownClass()

    def setUp(self):
        self.test_db.bind(MODELS, bind_refs=False, bind_backrefs=False)
        self.test_db.connect()
        self.test_db.create_tables(MODELS)
        self.controller = SystemConfigController

    def tearDown(self):
        self.test_db.drop_tables(MODELS)
        self.test_db.close()

    def assert_db_value(self, key, value):
        config_db_value = Config.get_entry('ESAFE_{}'.format(key), None)
        self.assertEqual(value, config_db_value)

    def test_doorbell_config(self):
        config_dto = self.controller.get_doorbell_config()
        self.assertEqual(True, config_dto.enabled)

        self.assert_db_value('doorbell_enabled', True)

        config_dto = SystemDoorbellConfigDTO(enabled=False)
        self.controller.save_doorbell_config(config_dto)

        self.assert_db_value('doorbell_enabled', False)

        config_dto_loaded = self.controller.get_doorbell_config()
        self.assertEqual(False, config_dto_loaded.enabled)

    def test_rfid_config(self):
        config_dto = self.controller.get_rfid_config()
        self.assertEqual(True, config_dto.enabled)
        self.assertEqual(False, config_dto.security_enabled)
        self.assertEqual(4, config_dto.max_tags)

        self.assert_db_value('rfid_enabled', True)
        self.assert_db_value('rfid_security_enabled', False)
        self.assert_db_value('max_rfid', 4)

        config_dto = SystemRFIDConfigDTO(enabled=False, security_enabled=True, max_tags=3)
        self.controller.save_rfid_config(config_dto)

        self.assert_db_value('rfid_enabled', False)
        self.assert_db_value('rfid_security_enabled', True)
        self.assert_db_value('max_rfid', 3)

        config_dto_loaded = self.controller.get_rfid_config()
        self.assertEqual(config_dto, config_dto_loaded)
        
    def test_rfid_sector_block_config(self):
        config_dto = self.controller.get_rfid_sector_block_config()
        self.assertEqual(1, config_dto.rfid_sector_block)

        self.assert_db_value('rfid_sector_block', 1)

        config_dto = SystemRFIDSectorBlockConfigDTO(rfid_sector_block=37)
        self.controller.save_rfid_sector_block_config(config_dto)

        self.assert_db_value('rfid_sector_block', 37)

        config_dto_loaded = self.controller.get_rfid_sector_block_config()
        self.assertEqual(config_dto, config_dto_loaded)

    def test_global_config(self):
        config_dto = self.controller.get_global_config()
        self.assertEqual('ESAFE', config_dto.device_name)
        self.assertEqual('BE', config_dto.country)
        self.assertEqual('', config_dto.postal_code)
        self.assertEqual('', config_dto.city)
        self.assertEqual('', config_dto.street)
        self.assertEqual('', config_dto.house_number)
        self.assertEqual('English', config_dto.language)

        self.assert_db_value('device_name', 'ESAFE')
        self.assert_db_value('country', 'BE')
        self.assert_db_value('postal_code', '')
        self.assert_db_value('city', '')
        self.assert_db_value('street', '')
        self.assert_db_value('house_number', '')
        self.assert_db_value('language', 'English')

        config_dto = SystemGlobalConfigDTO(device_name='Testerken',
                                           country='testland',
                                           postal_code='8790',
                                           city='test-city',
                                           street='test-street',
                                           house_number='37',
                                           language='test-lang'
                                           )
        self.controller.save_global_config(config_dto)

        self.assert_db_value('device_name', 'Testerken')
        self.assert_db_value('country', 'testland')
        self.assert_db_value('postal_code', '8790')
        self.assert_db_value('city', 'test-city')
        self.assert_db_value('street', 'test-street')
        self.assert_db_value('house_number', '37')
        self.assert_db_value('language', 'test-lang')

        config_dto_loaded = self.controller.get_global_config()
        self.assertEqual(config_dto, config_dto_loaded)
        
    def test_activate_user_config(self):
        config_dto = self.controller.get_activate_user_config()
        self.assertEqual(True, config_dto.change_first_name)
        self.assertEqual(True, config_dto.change_last_name)
        self.assertEqual(True, config_dto.change_language)
        self.assertEqual(False, config_dto.change_pin_code)

        self.assert_db_value('activate_change_first_name_enabled', True)
        self.assert_db_value('activate_change_last_name_enabled', True)
        self.assert_db_value('activate_change_language_enabled', True)
        self.assert_db_value('activate_change_user_code_enabled', False)

        config_dto = SystemActivateUserConfigDTO(change_first_name=False,
                                                 change_last_name=False,
                                                 change_language=False,
                                                 change_pin_code=True)
        self.controller.save_activate_user_config(config_dto)

        self.assert_db_value('activate_change_first_name_enabled', False)
        self.assert_db_value('activate_change_last_name_enabled', False)
        self.assert_db_value('activate_change_language_enabled', False)
        self.assert_db_value('activate_change_user_code_enabled', True)

        config_dto_loaded = self.controller.get_activate_user_config()
        self.assertEqual(config_dto, config_dto_loaded)
