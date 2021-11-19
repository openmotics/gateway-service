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
System Value helpers
"""
from __future__ import absolute_import

if False:  # MYPY
    from typing import Optional


class Temperature(object):
    @staticmethod
    def temperature_to_system_value(temperature):  # type: (Optional[float]) -> int
        if temperature is None:
            return 255
        return int((float(temperature) + 32) * 2)

    @staticmethod
    def system_value_to_temperature(system_value):  # type: (int) -> Optional[float]
        if system_value == 255:
            return None
        return float(system_value) / 2 - 32


class Humidity(object):
    @staticmethod
    def humidity_to_system_value(humidity):  # type: (Optional[float]) -> int
        if humidity is None:
            return 255
        return int(float(humidity) * 2)

    @staticmethod
    def system_value_to_humidity(system_value):  # type: (int) -> Optional[float]
        if system_value == 255:
            return None
        return float(system_value) / 2


class Timer(object):
    class EventTimerType(object):
        INACTIVE = 0
        PER_100_MS = 1
        PER_1_S = 2
        PER_1_M = 3

    @staticmethod
    def event_timer_type_to_seconds(timer_type, timer_value):  # type: (int, int) -> int
        if timer_type == Timer.EventTimerType.PER_1_S:
            return timer_value
        if timer_type == Timer.EventTimerType.PER_100_MS:
            return int(timer_value / 10.0)
        if timer_type == Timer.EventTimerType.PER_1_M:
            return timer_value * 60
        return 0


class Dimmer(object):
    PERCENTAGE_TO_SVT = {}
    SVT_TO_PERCENTAGE = {}
    for svt in range(256):
        percentage = int(svt / 255.0 * 100)
        SVT_TO_PERCENTAGE[svt] = percentage
        if percentage not in PERCENTAGE_TO_SVT:
            PERCENTAGE_TO_SVT[percentage] = svt
    print(SVT_TO_PERCENTAGE)
    print(PERCENTAGE_TO_SVT)

    @staticmethod
    def dimmer_to_system_value(dimmer):  # type: (int) -> int
        return Dimmer.PERCENTAGE_TO_SVT.get(dimmer, 0)

    @staticmethod
    def system_value_to_dimmer(system_value):  # type: (int) -> int
        return Dimmer.SVT_TO_PERCENTAGE.get(system_value, 0)
