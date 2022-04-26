from __future__ import absolute_import

import requests

from gateway.dto.sensor import SensorDTO
from gateway.dto.ventilation import VentilationDTO

if False:  # MYPY
    from typing import Any, Dict



class BaseApi(object):
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


class NotificationApi(BaseApi):
    def send(self, topic, message, type='USER'):
        data = {'source': 'plugin',
                'plugin': self._plugin_name,
                'type': type,
                'topic': topic,
                'message': message}
        self._api('POST', '/plugin/notification', json=data)


class SensorApi(BaseApi):
    def register(self, external_id, physical_quantity, config=None):
        data = {'source': 'plugin',
                'plugin': self._plugin_name,
                'external_id': external_id,
                'physical_quantity': physical_quantity,
                'config': config or {}}
        data = self._api('POST', '/plugin/sensor/register', json=data)
        return SensorDTO(data['id'], external_id=external_id)


class VentilationApi(BaseApi):
    def register_unit(self, external_id, config=None):
        data = {'source': 'plugin',
                'plugin': self._plugin_name,
                'external_id': external_id,
                'config': config or {}}
        data = self._api('POST', '/plugin/ventilation/register', json=data)
        return VentilationDTO(data['id'], external_id=external_id)
