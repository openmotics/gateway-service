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
Contains the definition of the power modules Api.
"""

from __future__ import absolute_import

from gateway.energy.energy_command import EnergyCommand, EnergyModuleType
from gateway.exceptions import UnsupportedException
from gateway.enums import EnergyEnums

if False:  # MYPY
    from typing import Optional

BROADCAST_ADDRESS = 255

NIGHT = 0
DAY = 1

NORMAL_MODE = 0
ADDRESS_MODE = 1


class EnergyAPI(object):
    @staticmethod
    def get_general_status(version):
        # type: (int) -> EnergyCommand
        """
        Get the general status of a power module.
        :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
        """
        if version == EnergyEnums.Version.POWER_MODULE:
            return EnergyCommand('G', 'GST', '', 'H')
        if version == EnergyEnums.Version.ENERGY_MODULE:
            return EnergyCommand('G', 'GST', '', 'B')
        raise UnsupportedException()

    @staticmethod
    def get_time_on(version):
        # type: (int) -> EnergyCommand
        """
        Get the time the power module is on (in s)
        :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
        """
        if version == EnergyEnums.Version.POWER_MODULE or version == EnergyEnums.Version.ENERGY_MODULE:
            return EnergyCommand('G', 'TON', '', 'L')
        raise UnsupportedException()

    @staticmethod
    def get_feed_status(version):
        # type: (int) -> EnergyCommand
        """
        Get the feed status of the power module (12x 0=low or 1=high)
        :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
        """
        if version == EnergyEnums.Version.POWER_MODULE:
            return EnergyCommand('G', 'FST', '', '8H')
        if version == EnergyEnums.Version.ENERGY_MODULE:
            return EnergyCommand('G', 'FST', '', '12I')
        raise UnsupportedException()

    @staticmethod
    def get_feed_counter(version):
        # type: (int) -> EnergyCommand
        """
        Get the feed counter of the power module
        :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
        """
        if version == EnergyEnums.Version.POWER_MODULE or version == EnergyEnums.Version.ENERGY_MODULE:
            return EnergyCommand('G', 'FCO', '', 'H')
        raise UnsupportedException()

    @staticmethod
    def get_status_p1(version):
        # type: (int) -> EnergyCommand
        """ Gets the status from a P1 concentrator """
        if version == EnergyEnums.Version.P1_CONCENTRATOR:
            return EnergyCommand('G', 'SP\x00', '', 'B', module_type=EnergyModuleType.C)
        raise UnsupportedException()

    @staticmethod
    def get_meter_p1(version, meter_type=None):
        # type: (int, Optional[int]) -> EnergyCommand
        """ Gets the meter id from a P1 concentrator """
        if version == EnergyEnums.Version.P1_CONCENTRATOR:
            if meter_type not in (1, 2):
                raise ValueError('Unknown meter type')
            return EnergyCommand('G', 'M{0}\x00'.format(meter_type), '', '224s', module_type=EnergyModuleType.C)
        raise UnsupportedException()

    @staticmethod
    def get_timestamp_p1(version):
        # type: (int) -> EnergyCommand
        """ Gets the timestamp from a P1 concentrator """
        if version == EnergyEnums.Version.P1_CONCENTRATOR:
            return EnergyCommand('G', 'TS\x00', '', '104s', module_type=EnergyModuleType.C)
        raise UnsupportedException()

    @staticmethod
    def get_gas_consumption_p1(version):
        # type: (int) -> EnergyCommand
        """ Gets the gas consumption from a P1 concentrator """
        if version == EnergyEnums.Version.P1_CONCENTRATOR:
            return EnergyCommand('G', 'cG\x00', '', '112s', module_type=EnergyModuleType.C)
        raise UnsupportedException()

    @staticmethod
    def get_consumption_tariff_p1(version, tariff_type=None):
        # type: (int, Optional[int]) -> EnergyCommand
        """ Gets the electricity consumption tariff from a P1 concentrator """
        if version == EnergyEnums.Version.P1_CONCENTRATOR:
            if tariff_type not in (1, 2):
                raise ValueError('Unknown tariff type')
            return EnergyCommand('G', 'c{0}\x00'.format(tariff_type), '', '112s', module_type=EnergyModuleType.C)
        raise UnsupportedException()

    @staticmethod
    def get_injection_tariff_p1(version, tariff_type=None):
        # type: (int, Optional[int]) -> EnergyCommand
        """ Gets the injection tariff from a P1 concentrator """
        if version == EnergyEnums.Version.P1_CONCENTRATOR:
            if tariff_type not in (1, 2):
                raise ValueError('Unknown tariff type')
            return EnergyCommand('G', 'i{0}\x00'.format(tariff_type), '', '112s', module_type=EnergyModuleType.C)
        raise UnsupportedException()

    @staticmethod
    def get_tariff_indicator_p1(version):
        # type: (int) -> EnergyCommand
        """ Gets the tariff indicator from a P1 concentrator """
        if version == EnergyEnums.Version.P1_CONCENTRATOR:
            return EnergyCommand('G', 'ti\x00', '', '32s', module_type=EnergyModuleType.C)
        raise UnsupportedException()

    @staticmethod
    def get_voltage(version, phase=None):
        # type: (int, Optional[int]) -> EnergyCommand
        """
        Get the voltage of a power module (in V)
        :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
        :param phase: Phase to read
        """
        if version in [EnergyEnums.Version.POWER_MODULE, EnergyEnums.Version.ENERGY_MODULE]:
            if phase is not None:
                raise ValueError('A phase is not supported')
            if version == EnergyEnums.Version.POWER_MODULE:
                return EnergyCommand('G', 'VOL', '', 'f')
            else:
                return EnergyCommand('G', 'VOL', '', '12f')
        if version == EnergyEnums.Version.P1_CONCENTRATOR:
            if phase is None:
                raise ValueError('A phase is required')
            return EnergyCommand('G', 'V{0}\x00'.format(phase), '', '56s', module_type=EnergyModuleType.C)
        raise UnsupportedException()

    @staticmethod
    def get_frequency(version):
        # type: (int) -> EnergyCommand
        """
        Get the frequency of a power module (in Hz)
        :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
        """
        if version == EnergyEnums.Version.POWER_MODULE:
            return EnergyCommand('G', 'FRE', '', 'f')
        if version == EnergyEnums.Version.ENERGY_MODULE:
            return EnergyCommand('G', 'FRE', '', '12f')
        raise UnsupportedException()

    @staticmethod
    def get_current(version, phase=None):
        # type: (int, Optional[int]) -> EnergyCommand
        """
        Get the current of a power module (12x in A)
        :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
        :param phase: Phase to read
        """
        if version in [EnergyEnums.Version.POWER_MODULE, EnergyEnums.Version.ENERGY_MODULE]:
            if phase is not None:
                raise ValueError('A phase is not supported')
            if version == EnergyEnums.Version.POWER_MODULE:
                return EnergyCommand('G', 'CUR', '', '8f')
            else:
                return EnergyCommand('G', 'CUR', '', '12f')
        if version == EnergyEnums.Version.P1_CONCENTRATOR:
            if phase is None:
                raise ValueError('A phase is required')
            return EnergyCommand('G', 'C{0}\x00'.format(phase), '', '40s', module_type=EnergyModuleType.C)
        raise UnsupportedException()

    @staticmethod
    def get_power(version):
        # type: (int) -> EnergyCommand
        """
        Get the power of a power module (12x in W)
        :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
        """
        if version == EnergyEnums.Version.POWER_MODULE:
            return EnergyCommand('G', 'POW', '', '8f')
        if version == EnergyEnums.Version.ENERGY_MODULE:
            return EnergyCommand('G', 'POW', '', '12f')
        raise UnsupportedException()

    @staticmethod
    def get_delivered_power(version):
        # type: (int) -> EnergyCommand
        """ Gets the delivered power of a P1 concentrator """
        if version == EnergyEnums.Version.P1_CONCENTRATOR:
            return EnergyCommand('G', 'PD\x00', '', '72s', module_type=EnergyModuleType.C)
        raise UnsupportedException()

    @staticmethod
    def get_received_power(version):
        # type: (int) -> EnergyCommand
        """ Gets the reveived power of a P1 concentrator """
        if version == EnergyEnums.Version.P1_CONCENTRATOR:
            return EnergyCommand('G', 'PR\x00', '', '72s', module_type=EnergyModuleType.C)
        raise UnsupportedException()

    @staticmethod
    def get_normal_energy(version):
        # type: (int) -> EnergyCommand
        """
        Get the total energy measured by the power module (12x in Wh)
        :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
        """
        if version == EnergyEnums.Version.ENERGY_MODULE:
            return EnergyCommand('G', 'ENE', '', '12L')
        raise UnsupportedException()

    @staticmethod
    def get_day_energy(version):
        # type: (int) -> EnergyCommand
        """
        Get the energy measured during the day by the power module (12x in Wh)
        :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
        """
        if version == EnergyEnums.Version.POWER_MODULE:
            return EnergyCommand('G', 'EDA', '', '8L')
        if version == EnergyEnums.Version.ENERGY_MODULE:
            return EnergyCommand('G', 'EDA', '', '12L')
        if version == EnergyEnums.Version.P1_CONCENTRATOR:
            return EnergyCommand('G', 'c1\x00', '', '112s', module_type=EnergyModuleType.C)
        raise UnsupportedException()

    @staticmethod
    def get_night_energy(version):
        # type: (int) -> EnergyCommand
        """
        Get the energy measured during the night by the power module (12x in Wh)
        :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
        """
        if version == EnergyEnums.Version.POWER_MODULE:
            return EnergyCommand('G', 'ENI', '', '8L')
        if version == EnergyEnums.Version.ENERGY_MODULE:
            return EnergyCommand('G', 'ENI', '', '12L')
        if version == EnergyEnums.Version.P1_CONCENTRATOR:
            return EnergyCommand('G', 'c2\x00', '', '112s', module_type=EnergyModuleType.C)
        raise UnsupportedException()

    @staticmethod
    def set_day_night(version):
        """
        Set the power module in night (0) or day (1) mode.
        :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
        """
        if version == EnergyEnums.Version.POWER_MODULE:
            return EnergyCommand('S', 'SDN', '8b', '')
        if version == EnergyEnums.Version.ENERGY_MODULE:
            return EnergyCommand('S', 'SDN', '12b', '')
        raise UnsupportedException()

    @staticmethod
    def get_sensor_types(version):
        # type: (int) -> EnergyCommand
        """
        Get the sensor types used on the power modules (8x sensor type).
        :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
        """
        if version == EnergyEnums.Version.POWER_MODULE:
            return EnergyCommand('G', 'CSU', '', '8b')
        if version == EnergyEnums.Version.ENERGY_MODULE:
            raise UnsupportedException("Getting sensor types is not applicable for the 12 port modules.")
        raise UnsupportedException()

    @staticmethod
    def set_sensor_types(version):
        # type: (int) -> EnergyCommand
        """
        Set the sensor types used on the power modules (8x sensor type).
        :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
        """
        if version == EnergyEnums.Version.POWER_MODULE:
            return EnergyCommand('S', 'CSU', '8b', '')
        if version == EnergyEnums.Version.ENERGY_MODULE:
            raise UnsupportedException("Setting sensor types is not applicable for the 12 port modules.")
        raise UnsupportedException()

    @staticmethod
    def set_current_clamp_factor(version):
        # type: (int) -> EnergyCommand
        """
        Sets the current clamp factor.
        :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
        """
        if version == EnergyEnums.Version.POWER_MODULE:
            raise UnsupportedException("Setting clamp factor is not applicable for the 8 port modules.")
        if version == EnergyEnums.Version.ENERGY_MODULE:
            return EnergyCommand('S', 'CCF', '12f', '')
        raise UnsupportedException()

    @staticmethod
    def set_current_inverse(version):
        # type: (int) -> EnergyCommand
        """
        Sets the current inverse.
        :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
        """
        if version == EnergyEnums.Version.POWER_MODULE:
            raise UnsupportedException("Setting current inverse is not applicable for the 8 port modules.")
        if version == EnergyEnums.Version.ENERGY_MODULE:
            return EnergyCommand('S', 'SCI', '=12B', '')
        raise UnsupportedException()

    # Below are the more advanced function (12p module only)

    @staticmethod
    def get_voltage_sample_time(version):
        # type: (int) -> EnergyCommand
        """
        Gets a voltage sample (time - oscilloscope view)
        :param version: power api version
        """
        if version == EnergyEnums.Version.ENERGY_MODULE:
            return EnergyCommand('G', 'VST', '2b', '50f')
        if version == EnergyEnums.Version.POWER_MODULE:
            raise UnsupportedException("Getting a voltage sample (time) is not applicable for the 8 port modules.")
        raise UnsupportedException()

    @staticmethod
    def get_current_sample_time(version):
        # type: (int) -> EnergyCommand
        """
        Gets a current sample (time - oscilloscope view)
        :param version: power api version
        """
        if version == EnergyEnums.Version.ENERGY_MODULE:
            return EnergyCommand('G', 'CST', '2b', '50f')
        if version == EnergyEnums.Version.POWER_MODULE:
            raise UnsupportedException("Getting a current sample (time) is not applicable for the 8 port modules.")
        raise UnsupportedException()

    @staticmethod
    def get_voltage_sample_frequency(version):
        # type: (int) -> EnergyCommand
        """
        Gets a voltage sample (frequency)
        :param version: power api version
        """
        if version == EnergyEnums.Version.ENERGY_MODULE:
            return EnergyCommand('G', 'VSF', '2b', '40f')
        if version == EnergyEnums.Version.POWER_MODULE:
            raise UnsupportedException("Getting a voltage sample (frequency) is not applicable for the 8 port modules.")
        raise UnsupportedException()

    @staticmethod
    def get_current_sample_frequency(version):
        # type: (int) -> EnergyCommand
        """
        Gets a current sample (frequency)
        :param version: power api version
        """
        if version == EnergyEnums.Version.ENERGY_MODULE:
            return EnergyCommand('G', 'CSF', '2b', '40f')
        if version == EnergyEnums.Version.POWER_MODULE:
            raise UnsupportedException("Getting a current sample (frequency) is not applicable for the 8 port modules.")
        raise UnsupportedException()

    @staticmethod
    def read_eeprom(version, length):
        # type: (int, int) -> EnergyCommand
        """
        Reads data from the eeprom
        :param version: power api version
        :param length: Amount of bytes to be read - must be equal to the actual length argument
        """
        if version == EnergyEnums.Version.ENERGY_MODULE:
            return EnergyCommand('G', 'EEP', '2H', '{0}B'.format(length))
        if version == EnergyEnums.Version.POWER_MODULE:
            raise UnsupportedException("Reading eeprom is not possible for the 8 port modules.")
        raise UnsupportedException()

    @staticmethod
    def write_eeprom(version, length):
        # type: (int, int) -> EnergyCommand
        """
        Write data to the eeprom
        :param version: power api version
        :param length: Amount of bytes to be read - must be equal to the actual amount of bytes written
        """
        if version == EnergyEnums.Version.ENERGY_MODULE:
            return EnergyCommand('S', 'EEP', '1H{0}B'.format(length), '')
        if version == EnergyEnums.Version.POWER_MODULE:
            raise UnsupportedException("Writing eeprom is not possible for the 8 port modules.")
        raise UnsupportedException()

    @staticmethod
    def set_board_options(version):
        # type: (int) -> EnergyCommand
        """
        Set the board options
        :param version: power api version
        """
        if version == EnergyEnums.Version.ENERGY_MODULE:
            return EnergyCommand('S', 'SBO', '4B', '')
        raise UnsupportedException()

    # Below are the address mode functions.

    @staticmethod
    def set_addressmode(version):
        # type: (int) -> EnergyCommand
        """ Set the address mode of the power module, 1 = address mode, 0 = normal mode """
        if version == EnergyEnums.Version.P1_CONCENTRATOR:
            return EnergyCommand('S', 'AGT', 'b', '', module_type=EnergyModuleType.C)
        return EnergyCommand('S', 'AGT', 'b', '')

    @staticmethod
    def want_an_address(version):
        # type: (int) -> EnergyCommand
        """ The Want An Address command, send by the power modules in address mode. """
        if version == EnergyEnums.Version.POWER_MODULE:
            return EnergyCommand('S', 'WAA', '', '')
        if version == EnergyEnums.Version.ENERGY_MODULE:
            return EnergyCommand('S', 'WAD', '', '')
        if version == EnergyEnums.Version.P1_CONCENTRATOR:
            return EnergyCommand('S', 'WAD', '', '', module_type=EnergyModuleType.C)
        raise UnsupportedException()

    @staticmethod
    def set_address(version):
        # type: (int) -> EnergyCommand
        """ Reply on want_an_address, setting a new address for the power module. """
        if version == EnergyEnums.Version.P1_CONCENTRATOR:
            return EnergyCommand('S', 'SAD', 'b', '', module_type=EnergyModuleType.C)
        return EnergyCommand('S', 'SAD', 'b', '')

    @staticmethod
    def set_voltage():
        # type: () -> EnergyCommand
        """ Calibrate the voltage of the power module. """
        return EnergyCommand('S', 'SVO', 'f', '')

    @staticmethod
    def set_current():
        # type: () -> EnergyCommand
        """ Calibrate the voltage of the power module. """
        return EnergyCommand('S', 'SCU', 'f', '')

    # Below are the function to reset the kwh counters

    @staticmethod
    def reset_normal_energy(version):
        # type: (int) -> EnergyCommand
        """
        Reset the total energy measured by the power module.
        :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
        """
        if version == EnergyEnums.Version.POWER_MODULE:
            return EnergyCommand('S', 'ENE', '9B', '')
        if version == EnergyEnums.Version.ENERGY_MODULE:
            return EnergyCommand('S', 'ENE', 'B12L', '')
        raise UnsupportedException()

    @staticmethod
    def reset_day_energy(version):
        # type: (int) -> EnergyCommand
        """
        Reset the energy measured during the day by the power module.
        :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
        """
        if version == EnergyEnums.Version.POWER_MODULE:
            return EnergyCommand('S', 'EDA', '9B', '')
        if version == EnergyEnums.Version.ENERGY_MODULE:
            return EnergyCommand('S', 'EDA', 'B12L', '')
        raise UnsupportedException()

    @staticmethod
    def reset_night_energy(version):
        # type: (int) -> EnergyCommand
        """
        Reset the energy measured during the night by the power module.
        :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
        """
        if version == EnergyEnums.Version.POWER_MODULE:
            return EnergyCommand('S', 'ENI', '9B', '')
        if version == EnergyEnums.Version.ENERGY_MODULE:
            return EnergyCommand('S', 'ENI', 'B12L', '')
        raise UnsupportedException()

    # Below are the bootloader functions

    @staticmethod
    def bootloader_goto(version):
        # type: (int) -> EnergyCommand
        """ Go to bootloader and wait for a number of seconds (b parameter) """
        if version == EnergyEnums.Version.P1_CONCENTRATOR:
            return EnergyCommand('S', 'RES', 'B', '', module_type=EnergyModuleType.C)
        return EnergyCommand('S', 'BGT', 'B', '')

    @staticmethod
    def bootloader_read_id():
        # type: () -> EnergyCommand
        """ Get the device id """
        return EnergyCommand('G', 'BRI', '', '8B')

    @staticmethod
    def bootloader_write_code(version):
        # type: (int) -> EnergyCommand
        """
        Write code
        :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
        """
        if version == EnergyEnums.Version.POWER_MODULE:
            return EnergyCommand('S', 'BWC', '195B', '')
        if version == EnergyEnums.Version.ENERGY_MODULE:
            return EnergyCommand('S', 'BWC', '132B', '')
        raise UnsupportedException()

    @staticmethod
    def bootloader_erase_code():
        # type: () -> EnergyCommand
        """ Erase the code on a given page. """
        return EnergyCommand('S', 'BEC', 'H', '')

    @staticmethod
    def bootloader_write_configuration():
        # type: () -> EnergyCommand
        """ Write configuration """
        return EnergyCommand('S', 'BWF', '24B', '')

    @staticmethod
    def bootloader_jump_application():
        # type: () -> EnergyCommand
        """ Go from bootloader to applications """
        return EnergyCommand('S', 'BJA', '', '')

    @staticmethod
    def get_version(version):
        # type: (int) -> EnergyCommand
        """ Get the current version of the power module firmware """
        if version == EnergyEnums.Version.P1_CONCENTRATOR:
            return EnergyCommand('G', 'FVE', '', '4B', module_type=EnergyModuleType.C)
        return EnergyCommand('G', 'FIV', '', '16s')

    # Below are the debug functions

    @staticmethod
    def raw_command(mode, command, num_bytes):
        # type: (str, str, int) -> EnergyCommand
        """ Create a EnergyCommand for debugging purposes. """
        return EnergyCommand(mode, command, '%dB' % num_bytes, None)
