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
Config Mapper
"""
from __future__ import absolute_import
from gateway.dto import ConfigDTO
from gateway.models import Config

if False:  # MYPY
    from typing import List


class ConfigMapper(object):

    @staticmethod
    def orm_to_dto(orm_object):  # type: (Config) -> ConfigDTO
        config_dto = ConfigDTO(
            setting=orm_object.setting,
            data=orm_object.data
        )
        return config_dto

    @staticmethod
    def dto_to_orm(config_dto, fields):  # type: (ConfigDTO, List[str]) -> Config
        # Look if there is a setting in the DB to take over the unchanged fields
        config = Config.get_or_none(setting=config_dto.setting)
        # if the setting is non existing, create a new setting with the mandatory fields that can be further filled with the config_dto fields
        if config is None:
            mandatory_fields = {'setting', 'data'}
            if not mandatory_fields.issubset(set(fields)):
                raise ValueError(
                    'Cannot create config without mandatory fields `{0}`'.format('`, `'.join(mandatory_fields)))

            config = Config(setting=config_dto.setting, data=config_dto.data)
        return config
