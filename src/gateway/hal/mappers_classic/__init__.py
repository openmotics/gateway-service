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

from gateway.hal.mappers_classic.global_feedback import GlobalFeedbackMapper
from gateway.hal.mappers_classic.group_action import GroupActionMapper
from gateway.hal.mappers_classic.input import InputMapper
from gateway.hal.mappers_classic.output import DimmerConfigurationMapper, \
    OutputMapper
from gateway.hal.mappers_classic.pulse_counter import PulseCounterMapper
from gateway.hal.mappers_classic.rtd10 import GlobalRTD10Mapper, RTD10Mapper
from gateway.hal.mappers_classic.sensor import SensorMapper
from gateway.hal.mappers_classic.shutter import ShutterMapper
from gateway.hal.mappers_classic.shutter_group import ShutterGroupMapper
from gateway.hal.mappers_classic.thermostat import PumpGroupMapper, \
    ThermostatGroupMapper, ThermostatMapper
