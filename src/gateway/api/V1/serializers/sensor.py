from __future__ import absolute_import

from gateway.dto.sensor import SensorDTO

if False:  # MYPY
    from typing import Any, Dict


class SensorConfigSerializer(object):
    pass


class SensorApiSerializer(object):
    @staticmethod
    def serialize(sensor_dto):
        # type: (SensorDTO) -> Dict[str,Any]
        data = {'id': sensor_dto.id,
                'name': sensor_dto.name,
                'room': sensor_dto.room,
                'in_use': sensor_dto.in_use or True}
        return data
