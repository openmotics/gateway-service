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

from gateway.dto.apartment import ApartmentDTO
from gateway.dto.box import ParcelBoxDTO, MailBoxDTO
from gateway.dto.delivery import DeliveryDTO
from gateway.dto.doorbell import DoorbellDTO
from gateway.dto.energy import RealtimeEnergyDTO, TotalEnergyDTO, EnergyModuleDTO
from gateway.dto.feedback_led import FeedbackLedDTO
from gateway.dto.global_feedback import GlobalFeedbackDTO
from gateway.dto.group_action import GroupActionDTO
from gateway.dto.input import InputDTO, InputStatusDTO
from gateway.dto.module import ModuleDTO
from gateway.dto.output import DimmerConfigurationDTO, OutputDTO, \
    OutputStatusDTO
from gateway.dto.pulse_counter import PulseCounterDTO
from gateway.dto.rfid import RfidDTO
from gateway.dto.room import RoomDTO
from gateway.dto.rtd10 import RTD10DTO, GlobalRTD10DTO
from gateway.dto.schedule import ScheduleDTO
from gateway.dto.sensor import MasterSensorDTO, SensorDTO, SensorSourceDTO, \
    SensorStatusDTO
from gateway.dto.shutter import ShutterDTO
from gateway.dto.shutter_group import ShutterGroupDTO
from gateway.dto.system_config import SystemDoorbellConfigDTO, SystemRFIDConfigDTO, \
    SystemRFIDSectorBlockConfigDTO, SystemTouchscreenConfigDTO, SystemGlobalConfigDTO, \
    SystemActivateUserConfigDTO
from gateway.dto.thermostat import PumpGroupDTO, ThermostatAircoStatusDTO, \
    ThermostatDTO, ThermostatGroupDTO, ThermostatGroupStatusDTO, \
    ThermostatStatusDTO
from gateway.dto.thermostat_schedule import ThermostatScheduleDTO
from gateway.dto.user import UserDTO
from gateway.dto.ventilation import VentilationDTO, VentilationSourceDTO, \
    VentilationStatusDTO
