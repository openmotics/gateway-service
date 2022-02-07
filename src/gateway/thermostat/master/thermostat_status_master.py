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
"""
The thermostats module contains classes to track the current state of the thermostats on
the master.
"""

from __future__ import absolute_import
from threading import Lock

from gateway.enums import ThermostatMode, ThermostatState


class ThermostatStatusMaster(object):
    """ Contains a cached version of the current thermostats of the controller. """

    def __init__(self, on_thermostat_change=None, on_thermostat_group_change=None):
        """
        Create a status object using a list of thermostats (can be None),
        and a refresh period: the refresh has to be invoked explicitly.
        """
        self._thermostats = {}
        self._on_thermostat_change = on_thermostat_change
        self._on_thermostat_group_change = on_thermostat_group_change
        self._merge_lock = Lock()

    def full_update(self, thermostats):
        """
        Update the status of the thermostats using a Thermostat status object (contains both global and individual info)

        Example object:
        {'thermostats_on': True,
         'automatic': True,
         'setpoint': 0,
         'cooling': True,
         'status': [{'id': 0,
                     'act': 25.4,
                     'csetp': 23.0,
                     'outside': '35.0,
                     'mode': 198,
                     'automatic': True,
                     'setpoint': 0,
                     'name': 'Living',
                     'sensor_nr': 15,
                     'airco': 115,
                     'output0': 32,
                     'output1': 0}]}
        """
        with self._merge_lock:
            new_status = {}
            state = ThermostatState.ON if thermostats['thermostats_on'] else ThermostatState.OFF
            mode = ThermostatMode.COOLING if thermostats['cooling'] else ThermostatMode.HEATING
            thermostats['mode'] = mode
            for status in thermostats['status']:
                status.update({'mode': mode,
                               'state': state,
                               'steering_power': (status['output0'] + status['output1']) // 2})
                new_status[status['id']] = status
            if not self._thermostats:
                self._report_group_change(mode=thermostats['mode'])
                for i in range(0, 32):
                    self._report_change(i, new_status.get(i))
            else:
                if mode != self._thermostats['mode']:
                    self._report_group_change(mode=mode)
                old_status = {t['id']: t for t in self._thermostats['status']}
                for thermostat_id in range(0, 32):
                    change = False
                    if (thermostat_id in old_status) != (thermostat_id in new_status):
                        change = True
                    elif thermostat_id in old_status and thermostat_id in new_status:
                        for key in old_status[thermostat_id]:
                            if old_status[thermostat_id][key] != new_status[thermostat_id][key]:
                                change = True
                                break
                    if change:
                        self._report_change(thermostat_id, new_status.get(thermostat_id))
            self._thermostats = thermostats

    def get_thermostats(self):
        return self._thermostats

    def _report_change(self, thermostat_id, status):
        if self._on_thermostat_change is not None and status is not None:
            self._on_thermostat_change(thermostat_id, {'preset': status['preset'],
                                                       'state': status['state'],
                                                       'mode': status['mode'],
                                                       'current_setpoint': status['csetp'],
                                                       'actual_temperature': status['act'],
                                                       'output_0': status['output0'],
                                                       'output_1': status['output1'],
                                                       'steering_power': status['steering_power']})

    def _report_group_change(self, mode):
        if self._on_thermostat_group_change is not None:
            self._on_thermostat_group_change({'mode': mode})
