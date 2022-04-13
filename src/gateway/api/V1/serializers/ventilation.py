from __future__ import absolute_import

from gateway.dto.ventilation import VentilationDTO, VentilationSourceDTO

if False:  # MYPY
    from typing import Any, Dict


class VentilationConfigSerializer(object):
    @staticmethod
    def deserialize(data):
        ventilation_dto = VentilationDTO(data.get('id'))
        ventilation_dto.name = data['name']
        ventilation_dto.room = data['room']
        if 'amount_of_levels' in data:
            ventilation_dto.amount_of_levels = data['amount_of_levels']
        if 'device' in data:
            ventilation_dto.device_vendor = data['device']['vendor']
            ventilation_dto.device_type = data['device']['type']
            ventilation_dto.device_serial = data['device']['serial']
        return ventilation_dto

    @staticmethod
    def serialize(ventilation_dto):
        # type: (VentilationDTO) -> Dict[str,Any]
        data = {'id': ventilation_dto.id,
                'name': ventilation_dto.name,
                'room': ventilation_dto.room,
                'amount_of_levels': ventilation_dto.amount_of_levels,
                'source': ventilation_dto.source.type,
                'device': {'vendor': ventilation_dto.device_vendor,
                           'type': ventilation_dto.device_type,
                           'serial': ventilation_dto.device_serial}}
        if ventilation_dto.source.type == 'plugin':
            data['external_id'] = ventilation_dto.external_id
        return data


class VentilationApiSerializer(object):
    @staticmethod
    def serialize(ventilation_dto):
        # type: (VentilationDTO) -> Dict[str,Any]
        data = {'id': ventilation_dto.id,
                'name': ventilation_dto.name,
                'room': ventilation_dto.room}
        return data
