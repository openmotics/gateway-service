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
(De)serializer helpers
"""
from toolbox import Toolbox

if False:  # MYPY
    from typing import Dict, Any, List, Optional


class SerializerToolbox(object):
    @staticmethod
    def filter_fields(data, fields):  # type: (Dict[str, Any], Optional[List[str]]) -> Dict[str, Any]
        if fields is None:
            return data
        return {field: data[field] for field in fields}

    @staticmethod
    def deserialize(dto, api_data, mapping):
        loaded_fields = []
        for data_field, (dto_field, default) in mapping.iteritems():
            if data_field in api_data:
                loaded_fields.append(dto_field)
                if default is None:
                    setattr(dto, dto_field, api_data[data_field])
                else:
                    setattr(dto, dto_field, Toolbox.nonify(api_data[data_field], default))
        return loaded_fields
