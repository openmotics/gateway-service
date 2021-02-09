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
from ioc import SetTestMode
from gateway.dto import InputDTO
from gateway.hal.mappers_core import InputMapper
from master.core.basic_action import BasicAction
from master.core.memory_models import InputConfiguration, InputModuleConfiguration
from mocked_core_helper import MockedCore


class InputCoreMapperTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.mocked_core = MockedCore()
        self.memory = self.mocked_core.memory

        # Remove read-only flags from device_type for testing purposes below
        if hasattr(InputModuleConfiguration, '_device_type'):
            InputModuleConfiguration._device_type._read_only = False
        else:
            InputModuleConfiguration.device_type._read_only = False

    def test_mapping_basic(self):
        orm = InputMapper.dto_to_orm(InputDTO(id=0,
                                              name='input 0',
                                              event_enabled=True,
                                              invert=True),
                                     fields=['name', 'event_enabled', 'invert'])
        self.assertEqual(0, orm.id)
        self.assertEqual('input 0', orm.name)
        self.assertFalse(orm.input_config.normal_open)

        dto = InputMapper.orm_to_dto(InputConfiguration.deserialize({'id': 1,
                                                                     'name': 'input 1',
                                                                     'input_config': {'normal_open': True},
                                                                     'module': {'id': 0,
                                                                                'device_type': 'b'}}))
        self.assertEqual(1, dto.id)
        self.assertEqual('input 1', dto.name)
        self.assertEqual('I', dto.module_type)
        self.assertFalse(dto.invert)

    def test_actions_non_configured_input(self):
        orm = InputCoreMapperTest._dto_to_orm(action=255, basic_actions=[])
        self._validate_orm(orm,
                           enable_press_and_release=True,
                           enable_1s_press=True,
                           enable_2s_press=True,
                           enable_double_press=True)

        dto = InputCoreMapperTest._orm_to_dto()
        self.assertEqual(255, dto.action)
        self.assertEqual([], dto.basic_actions)

        dto = InputCoreMapperTest._orm_to_dto(input_link={'output_id': 1023})
        self.assertEqual(255, dto.action)
        self.assertEqual([], dto.basic_actions)

    def test_actions_output_linked(self):
        orm = InputCoreMapperTest._dto_to_orm(action=123, basic_actions=[])
        self._validate_orm(orm,
                           has_direct_output_link=True,
                           in_use=True,
                           output_id=123)

        dto = InputCoreMapperTest._orm_to_dto(input_link={'output_id': 123,
                                                          'enable_press_and_release': False,
                                                          'enable_1s_press': False,
                                                          'enable_2s_press': False,
                                                          'enable_double_press': False})
        self.assertEqual(123, dto.action)
        self.assertEqual([], dto.basic_actions)

    def test_actions_delayed_press(self):
        orm = InputCoreMapperTest._dto_to_orm(action=240, basic_actions=[207, 1])
        self._validate_orm(orm,
                           in_use=True,
                           enable_2s_press=True,
                           basic_action_2s_press=True)
        self.assertEqual(BasicAction(action_type=19, action=0, device_nr=1), orm.basic_action_2s_press)

        dto = InputCoreMapperTest._orm_to_dto(input_link={'enable_press_and_release': False,
                                                          'enable_1s_press': False,
                                                          'enable_double_press': False},
                                              basic_action_2s_press=BasicAction(action_type=19, action=0, device_nr=1))
        self.assertEqual(240, dto.action)
        self.assertEqual([207, 1], dto.basic_actions)

    def test_actions_press(self):
        orm = InputCoreMapperTest._dto_to_orm(action=240, basic_actions=[2, 1])
        self._validate_orm(orm,
                           in_use=True,
                           enable_press_and_release=True,
                           basic_action_press=True)
        self.assertEqual(BasicAction(action_type=19, action=0, device_nr=1), orm.basic_action_press)

        dto = InputCoreMapperTest._orm_to_dto(input_link={'enable_1s_press': False,
                                                          'enable_2s_press': False,
                                                          'enable_double_press': False},
                                              basic_action_press=BasicAction(action_type=19, action=0, device_nr=1))
        self.assertEqual(240, dto.action)
        self.assertEqual([2, 1], dto.basic_actions)

    def test_actions_release(self):
        orm = InputCoreMapperTest._dto_to_orm(action=240, basic_actions=[236, 0, 2, 1, 236, 255])
        self._validate_orm(orm,
                           in_use=True,
                           enable_press_and_release=True,
                           basic_action_release=True)
        self.assertEqual(BasicAction(action_type=19, action=0, device_nr=1), orm.basic_action_release)

        dto = InputCoreMapperTest._orm_to_dto(input_link={'enable_1s_press': False,
                                                          'enable_2s_press': False,
                                                          'enable_double_press': False},
                                              basic_action_release=BasicAction(action_type=19, action=0, device_nr=1))
        self.assertEqual(240, dto.action)
        self.assertEqual([236, 0, 2, 1, 236, 255], dto.basic_actions)

    def test_actions_press_release(self):
        orm = InputCoreMapperTest._dto_to_orm(action=240, basic_actions=[2, 1, 236, 0, 2, 2, 236, 255])
        self._validate_orm(orm,
                           in_use=True,
                           enable_press_and_release=True,
                           basic_action_press=True,
                           basic_action_release=True)
        self.assertEqual(BasicAction(action_type=19, action=0, device_nr=1), orm.basic_action_press)
        self.assertEqual(BasicAction(action_type=19, action=0, device_nr=2), orm.basic_action_release)

        dto = InputCoreMapperTest._orm_to_dto(input_link={'enable_1s_press': False,
                                                          'enable_2s_press': False,
                                                          'enable_double_press': False},
                                              basic_action_press=BasicAction(action_type=19, action=0, device_nr=1),
                                              basic_action_release=BasicAction(action_type=19, action=0, device_nr=2))
        self.assertEqual(240, dto.action)
        self.assertEqual([2, 1, 236, 0, 2, 2, 236, 255], dto.basic_actions)

    def test_actions_invalid(self):
        with self.assertRaises(ValueError):
            InputCoreMapperTest._dto_to_orm(action=240, basic_actions=[161, 1])

    def _validate_orm(self, orm, **kwargs):
        self.assertEqual(kwargs.get('has_direct_output_link', False), orm.has_direct_output_link)
        self.assertEqual(kwargs.get('in_use', False), orm.in_use)
        self.assertEqual(kwargs.get('output_id', 1023), orm.input_link.output_id)
        self.assertEqual(kwargs.get('enable_press_and_release', False), orm.input_link.enable_press_and_release)
        self.assertEqual(kwargs.get('enable_1s_press', False), orm.input_link.enable_1s_press)
        self.assertEqual(kwargs.get('enable_2s_press', False), orm.input_link.enable_2s_press)
        self.assertEqual(kwargs.get('enable_double_press', False), orm.input_link.enable_double_press)
        self.assertEqual(kwargs.get('basic_action_press', False), orm.basic_action_press.in_use)
        self.assertEqual(kwargs.get('basic_action_release', False), orm.basic_action_release.in_use)
        self.assertEqual(kwargs.get('basic_action_1s_press', False), orm.basic_action_1s_press.in_use)
        self.assertEqual(kwargs.get('basic_action_2s_press', False), orm.basic_action_2s_press.in_use)
        self.assertEqual(kwargs.get('basic_action_double_press', False), orm.basic_action_double_press.in_use)

    @staticmethod
    def _dto_to_orm(action, basic_actions):
        return InputMapper.dto_to_orm(InputDTO(id=0,
                                               name='input 0',
                                               action=action,
                                               basic_actions=basic_actions),
                                      fields=['name', 'action', 'basic_actions'])

    @staticmethod
    def _orm_to_dto(**kwargs):
        kwargs.update({'id': 0, 'name': 'input 0'})
        return InputMapper.orm_to_dto(InputConfiguration.deserialize(kwargs))
