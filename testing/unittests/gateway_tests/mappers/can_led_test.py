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
from ioc import SetTestMode
from gateway.dto import GlobalFeedbackDTO, FeedbackLedDTO
from gateway.hal.mappers_classic import GlobalFeedbackMapper
from master.classic.eeprom_models import CanLedConfiguration


class InputCoreMapperTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def test_mapping_basic(self):
        orm = GlobalFeedbackMapper.dto_to_orm(GlobalFeedbackDTO(id=0,
                                                                can_led_1=None,
                                                                can_led_2=FeedbackLedDTO(id=10,
                                                                                         function=FeedbackLedDTO.Functions.FB_B5_NORMAL),
                                                                can_led_3=None,
                                                                can_led_4=None))
        self.assertEqual(0, orm.id)
        self.assertEqual(255, orm.can_led_1_id)
        self.assertEqual('UNKNOWN', orm.can_led_1_function)
        self.assertEqual(10, orm.can_led_2_id)
        self.assertEqual('Fast blink B5', orm.can_led_2_function)
        self.assertEqual(255, orm.can_led_3_id)
        self.assertEqual('UNKNOWN', orm.can_led_3_function)
        self.assertEqual(255, orm.can_led_4_id)
        self.assertEqual('UNKNOWN', orm.can_led_4_function)

        dto = GlobalFeedbackMapper.orm_to_dto(CanLedConfiguration.deserialize({'id': 0,
                                                                               'can_led_1_id': 15,
                                                                               'can_led_1_function': 'On B8 Inverted',
                                                                               'can_led_2_id': 255,
                                                                               'can_led_2_function': 'UNKNOWN',
                                                                               'can_led_3_id': 255,
                                                                               'can_led_3_function': 'UNKNOWN',
                                                                               'can_led_4_id': 255,
                                                                               'can_led_4_function': 'UNKNOWN'
        }))
        self.assertEqual(0, dto.id)
        self.assertEqual(FeedbackLedDTO(id=15, function=FeedbackLedDTO.Functions.ON_B8_INVERTED), dto.can_led_1)
        self.assertEqual(FeedbackLedDTO(id=None, function=FeedbackLedDTO.Functions.UNKNOWN), dto.can_led_2)
        self.assertEqual(FeedbackLedDTO(id=None, function=FeedbackLedDTO.Functions.UNKNOWN), dto.can_led_3)
        self.assertEqual(FeedbackLedDTO(id=None, function=FeedbackLedDTO.Functions.UNKNOWN), dto.can_led_4)
