# Copyright (C) 2016 OpenMotics BV
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

import logging
from gateway.dto import ThermostatScheduleDTO, ThermostatDTO
from models import Feature

logger = logging.getLogger('openmotics')


class Migrator(object):

    @staticmethod
    def migrate_master_config_to_gateway():
        # TODO: Create & start up a Classic MasterController

        def is_valid(dto_):  # type: (ThermostatDTO) -> bool
            if dto_.output0 is None or dto_.output0 > 240:
                return False
            if dto_.pid_p is None:
                return False
            sensor = dto_.sensor
            if sensor is None or not (sensor < 32 or sensor == 240):
                return False
            for day in ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']:
                field_dto = getattr(dto_, 'auto_{0}'.format(day))  # type: ThermostatScheduleDTO
                if 95.5 in [field_dto.temp_night, field_dto.temp_day_2, field_dto.temp_day_1]:
                    return False
                if '42:30' in [field_dto.start_day_1, field_dto.end_day_1, field_dto.start_day_2, field_dto.end_day_2]:
                    return False
            return True

        classic_master_controller = None  # TODO
        gateway_thermostat_controller = None  # TODO

        try:
            # 0. check if migration already done
            feature = Feature.get(name='thermostats_gateway')
            if not feature.enabled:
                # 1. try to read all config from master and save it in the db
                try:
                    for mode in ['heating', 'cooling']:
                        all_fields = ['name']  # Extend with all fields
                        dtos = getattr(classic_master_controller, 'load_{0}_thermostats'.format(mode))()
                        getattr(gateway_thermostat_controller, 'save_{0}_thermostats'.format(mode))([(dto, all_fields) for dto in dtos
                                                                                                     if is_valid(dto)])
                except Exception:
                    logger.exception('Error occurred while migrating thermostats configuration from master eeprom.')
                    return False

                # 2. disable all thermostats on the master
                try:
                    for thermostat_id in xrange(32):
                        # TODO: use new master API to disable thermostat
                        # self._master_communicator.xyz
                        pass
                except Exception:
                    logger.exception('Error occurred while stopping master thermostats.')
                    return False

                # 3. write flag in database to enable gateway thermostats
                feature.enabled = True
                feature.save()
            return True
        except Exception:
            logger.exception('Error migrating master thermostats')
            return False
