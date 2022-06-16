from __future__ import absolute_import

import requests
import ujson as json

from gateway.dto.sensor import SensorDTO, SensorStatusDTO
from gateway.dto.ventilation import VentilationDTO, VentilationStatusDTO

if False:  # MYPY
    from typing import Any, Dict



class BaseSDK(object):
    def __init__(self, base_url, plugin_name):
        self._base_url = base_url
        self._plugin_name = plugin_name
        self._request_kwargs = {
            'timeout': 30.0,
            'headers': {'User-Agent': 'Plugin {0}'.format(self._plugin_name)}
        }  # type: Dict[str,Any]

    def _api(self, method, path, **kwargs):
        kwargs.update(self._request_kwargs)
        response = requests.request(method, '{0}/{1}'.format(self._base_url, path.strip('/')), **kwargs)
        response.raise_for_status()
        return response.json()


class NotificationSDK(BaseSDK):
    def send(self, topic, message, type='USER'):
        data = {'source': 'plugin',
                'plugin': self._plugin_name,
                'type': type,
                'topic': topic,
                'message': message}
        self._api('POST', '/plugin/notification', json=data)


class SensorSDK(BaseSDK):
    def register_temperature_celcius(self, external_id, config=None):
        return self.register(external_id, 'temperature', 'celcius', config)

    def register_humidity_percent(self, external_id, config=None):
        return self.register(external_id, 'humidity', 'percent', config)

    def register_co2_ppm(self, external_id, config=None):
        return self.register(external_id, 'co2', 'parts_per_million', config)

    def register(self, external_id, physical_quantity, unit, config=None):
        data = {'source': 'plugin',
                'plugin': self._plugin_name,
                'external_id': external_id,
                'physical_quantity': physical_quantity,
                'unit': unit,
                'config': config or {}}
        data = self._api('POST', '/plugin/sensor/register', json=data)
        return SensorDTO(data['id'], external_id=external_id)

    def set_status(self, sensor_id, value):
        status = {'id': sensor_id, 'value': value}
        # TODO replace with proper sensor api
        data = self._api('POST', '/set_sensor_status', params={'status': json.dumps(status)})
        if data.get('success', False) is True:
            return SensorStatusDTO(data['status']['id'],
                                   value=data['status']['value'])
        else:
            return None


class VentilationSDK(BaseSDK):
    def register(self, external_id, config=None):
        data = {'source': 'plugin',
                'plugin': self._plugin_name,
                'external_id': external_id,
                'config': config or {}}
        data = self._api('POST', '/plugin/ventilation/register', json=data)
        return VentilationDTO(data['id'], external_id=external_id)

    def set_auto(self, ventilation_id, **kwargs):
        return self.set_status(ventilation_id, VentilationStatusDTO.Mode.AUTO, **kwargs)

    def set_manual(self, ventilation_id, **kwargs):
        return self.set_status(ventilation_id, VentilationStatusDTO.Mode.MANUAL, **kwargs)

    def set_status(self, ventilation_id, mode, level=None, timer=None, remaining_time=None):
        status = {'id': ventilation_id, 'mode': mode}
        for key, value in [('level', level),
                           ('timer', timer),
                           ('remaining_time', remaining_time)]:
            if value is not None:
                status.update({key: value})
        # TODO replace with proper ventilation api
        data = self._api('POST', '/set_ventilation_status', params={'status': json.dumps(status)})
        if data.get('success', False) is True:
            return VentilationStatusDTO(data['status']['id'],
                                        mode=data['status']['mode'],
                                        level=data['status']['mode'],
                                        timer=data['status']['timer'],
                                        remaining_time=data['status']['remaining_time'])
        else:
            return None
