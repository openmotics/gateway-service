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

"""
Output Mapper
"""
from __future__ import absolute_import
from toolbox import Toolbox
from gateway.dto.output import OutputDTO
from gateway.dto.feedback_led import FeedbackLedDTO
from master.classic.eeprom_controller import EepromModel
from master.classic.eeprom_models import OutputConfiguration

if False:  # MYPY
    from typing import List


class OutputMapper(object):
    WORD_MAX = 2 ** 16 - 1
    BYTE_MAX = 255

    @staticmethod
    def orm_to_dto(orm_object):  # type: (EepromModel) -> OutputDTO
        data = orm_object.serialize()
        return OutputDTO(id=data['id'],
                         module_type=data['module_type'],
                         name=data['name'],
                         timer=Toolbox.nonify(data['timer'], OutputMapper.WORD_MAX),
                         floor=Toolbox.nonify(data['floor'], OutputMapper.BYTE_MAX),
                         output_type=data['type'],
                         lock_bit_id=Toolbox.nonify(data['lock_bit_id'], OutputMapper.BYTE_MAX),
                         can_led_1=FeedbackLedDTO(id=Toolbox.nonify(data['can_led_1_id'], OutputMapper.BYTE_MAX),
                                                  function=data['can_led_1_function']),
                         can_led_2=FeedbackLedDTO(id=Toolbox.nonify(data['can_led_2_id'], OutputMapper.BYTE_MAX),
                                                  function=data['can_led_2_function']),
                         can_led_3=FeedbackLedDTO(id=Toolbox.nonify(data['can_led_3_id'], OutputMapper.BYTE_MAX),
                                                  function=data['can_led_3_function']),
                         can_led_4=FeedbackLedDTO(id=Toolbox.nonify(data['can_led_4_id'], OutputMapper.BYTE_MAX),
                                                  function=data['can_led_4_function']))

    @staticmethod
    def dto_to_orm(output_dto, fields):  # type: (OutputDTO, List[str]) -> EepromModel
        data = {'id': output_dto.id}
        for dto_field, data_field in {'module_type': 'module_type',
                                      'name': 'name',
                                      'output_type': 'type'}.items():
            if dto_field in fields:
                data[data_field] = getattr(output_dto, dto_field)
        for dto_field, (data_field, default) in {'timer': ('timer', OutputMapper.WORD_MAX),
                                                 'floor': ('floor', OutputMapper.BYTE_MAX),
                                                 'lock_bit_id': ('lock_bit_id', OutputMapper.BYTE_MAX)}.items():
            if dto_field in fields:
                data[data_field] = Toolbox.denonify(getattr(output_dto, dto_field), default)
        for i in range(4):
            base_field = 'can_led_{0}'.format(i + 1)
            if base_field in fields:
                id_field = '{0}_id'.format(base_field)
                function_field = '{0}_function'.format(base_field)
                data[id_field] = getattr(output_dto, base_field).id
                data[function_field] = getattr(output_dto, base_field).function
        return OutputConfiguration.deserialize(data)
