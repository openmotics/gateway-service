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

import mock
import unittest
from gateway.api.serializers import SystemDoorbellConfigSerializer, SystemRFIDConfigSerializer, SystemRFIDSectorBlockConfigSerializer, \
    SystemTouchscreenConfigSerializer, SystemGlobalConfigSerializer, SystemActivateUserConfigSerializer
from gateway.user_controller import UserController
from ioc import SetTestMode, SetUpTestInjections



class SystemConfigSerializerTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.user_controller = mock.Mock(UserController)
        SetUpTestInjections(user_controller=self.user_controller)

    def serializer_test(self, serializer, serial_data):
        _ = self
        dto = serializer.deserialize(serial_data)
        dto_serial = serializer.serialize(dto)
        self.assertEqual(serial_data, dto_serial)

    def test_serialize_deserialzie(self):
        serial = {
            'enabled': True
        }
        self.serializer_test(SystemDoorbellConfigSerializer, serial)

        serial = {
            'enabled': True,
            'security_enabled': False,
            'max_tags': 4
        }
        self.serializer_test(SystemRFIDConfigSerializer, serial)

        # other order
        serial = {
            'security_enabled': False,
            'max_tags': 4,
            'enabled': True
        }
        self.serializer_test(SystemRFIDConfigSerializer, serial)

        serial = {
            'rfid_sector_block': 3
        }
        self.serializer_test(SystemRFIDSectorBlockConfigSerializer, serial)

        serial = {
            'calibrated': True
        }
        self.serializer_test(SystemTouchscreenConfigSerializer, serial)

        serial = {
            'device_name': 'test',
            'country': 'belgium',
            'postal_code': '8790',
            'city': 'waregem',
            'street': 'vlasstraat',
            'house_number': '59',
            'language': 'EN',
        }
        self.serializer_test(SystemGlobalConfigSerializer, serial)

        serial = {
            'change_first_name_enabled': True,
            'change_last_name_enabled': False,
            'change_language_enabled': True,
            'change_user_code_enabled': False
        }
        self.serializer_test(SystemActivateUserConfigSerializer, serial)
