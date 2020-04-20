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
HeatingThermostat Mapper
"""
from toolbox import Toolbox
from gateway.dto import HeatingThermostatDTO, ThermostatScheduleDTO
from master.eeprom_controller import EepromModel
from master.eeprom_models import ThermostatConfiguration

if False:  # MYPY
    from typing import List


class HeatingThermostatMapper(object):
    BYTE_MAX = 255

    @staticmethod
    def orm_to_dto(orm_object):  # type: (EepromModel) -> HeatingThermostatDTO
        data = orm_object.serialize()
        kwargs = {'name': data['name'],
                  'permanent_manual': data['permanent_manual']}
        for i in range(6):
            field = 'setp{0}'.format(i)
            kwargs[field] = data[field]
        for field in ['sensor', 'output0', 'output1', 'pid_p', 'pid_i', 'pid_d', 'pid_int', 'room']:
            kwargs[field] = Toolbox.nonify(data[field], HeatingThermostatMapper.BYTE_MAX)
        for day in ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']:
            field = 'auto_{0}'.format(day)
            kwargs[field] = ThermostatScheduleDTO(temp_night=data[field][0],
                                                  start_day_1=data[field][1],
                                                  end_day_1=data[field][2],
                                                  temp_day_1=data[field][3],
                                                  start_day_2=data[field][4],
                                                  end_day_2=data[field][5],
                                                  temp_day_2=data[field][6])
        return HeatingThermostatDTO(id=data['id'],
                                    **kwargs)

    @staticmethod
    def dto_to_orm(thermostat_dto, fields):  # type: (HeatingThermostatDTO, List[str]) -> EepromModel
        data = {'id': thermostat_dto.id}
        for field in ['name', 'permanent_manual'] + ['setp{0}'.format(i) for i in range(6)]:
            if field in fields:
                data[field] = getattr(thermostat_dto, field)
        for field in ['sensor', 'output0', 'output1', 'pid_p', 'pid_i', 'pid_d', 'pid_int', 'room']:
            if field in fields:
                data[field] = Toolbox.denonify(getattr(thermostat_dto, field), HeatingThermostatMapper.BYTE_MAX)
        for day in ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']:
            field = 'auto_{0}'.format(day)
            if field not in fields:
                continue
            dto_data = getattr(thermostat_dto, field)  # type: ThermostatScheduleDTO
            if dto_data is None:
                continue
            data[field] = [dto_data.temp_night,
                           dto_data.start_day_1,
                           dto_data.end_day_1,
                           dto_data.temp_day_1,
                           dto_data.start_day_2,
                           dto_data.end_day_2,
                           dto_data.temp_day_2]
        return ThermostatConfiguration.deserialize(data)
