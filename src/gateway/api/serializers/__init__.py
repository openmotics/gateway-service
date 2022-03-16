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

from gateway.api.serializers.energy import EnergyModuleSerializer
from gateway.api.serializers.global_feedback import GlobalFeedbackSerializer
from gateway.api.serializers.group_action import GroupActionSerializer
from gateway.api.serializers.input import InputSerializer, InputStateSerializer
from gateway.api.serializers.module import ModuleSerializer
from gateway.api.serializers.output import DimmerConfigurationSerializer, \
    OutputSerializer, OutputStateSerializer
from gateway.api.serializers.pulse_counter import PulseCounterSerializer
from gateway.api.serializers.room import RoomSerializer
from gateway.api.serializers.rtd10 import GlobalRTD10Serializer, \
    RTD10Serializer
from gateway.api.serializers.schedule import ScheduleSerializer
from gateway.api.serializers.sensor import SensorSerializer, \
    SensorStatusSerializer
from gateway.api.serializers.shutter import ShutterSerializer
from gateway.api.serializers.shutter_group import ShutterGroupSerializer
from gateway.api.serializers.thermostat import LegacyThermostatGroupStatusSerializer, \
    PumpGroupSerializer, ThermostatAircoStatusSerializer, \
    ThermostatGroupSerializer, ThermostatGroupStatusSerializer, \
    ThermostatSerializer
from gateway.api.serializers.user import UserSerializer
from gateway.api.serializers.ventilation import VentilationSerializer, \
    VentilationStatusSerializer
