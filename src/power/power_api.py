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

from power.power_command import PowerCommand, PowerModuleType
from gateway.exceptions import UnsupportedException

if False:  # MYPY
    from typing import Optional

BROADCAST_ADDRESS = 255

NIGHT = 0
DAY = 1

NORMAL_MODE = 0
ADDRESS_MODE = 1

POWER_MODULE = 8
ENERGY_MODULE = 12
P1_CONCENTRATOR = 1

NUM_PORTS = {POWER_MODULE: 8,
             ENERGY_MODULE: 12,
             P1_CONCENTRATOR: 8}

LARGEST_MODULE_TYPE = [module_type for module_type in NUM_PORTS.keys()
                       if NUM_PORTS[module_type] == max(*list(NUM_PORTS.values()))][0]


def get_general_status(version):
    # type: (int) -> PowerCommand
    """
    Get the general status of a power module.
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE:
        return PowerCommand('G', 'GST', '', 'H')
    if version == ENERGY_MODULE:
        return PowerCommand('G', 'GST', '', 'B')
    raise UnsupportedException()


def get_time_on(version):
    # type: (int) -> PowerCommand
    """
    Get the time the power module is on (in s)
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE or version == ENERGY_MODULE:
        return PowerCommand('G', 'TON', '', 'L')
    raise UnsupportedException()


def get_feed_status(version):
    # type: (int) -> PowerCommand
    """
    Get the feed status of the power module (12x 0=low or 1=high)
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE:
        return PowerCommand('G', 'FST', '', '8H')
    if version == ENERGY_MODULE:
        return PowerCommand('G', 'FST', '', '12I')
    raise UnsupportedException()


def get_feed_counter(version):
    # type: (int) -> PowerCommand
    """
    Get the feed counter of the power module
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE or version == ENERGY_MODULE:
        return PowerCommand('G', 'FCO', '', 'H')
    raise UnsupportedException()


def get_status_p1(version):
    # type: (int) -> PowerCommand
    """ Gets the status from a P1 concentrator """
    if version == P1_CONCENTRATOR:
        return PowerCommand('G', 'SP\x00', '', 'B', module_type=PowerModuleType.C)
    raise UnsupportedException()


def get_meter_p1(version, meter_type=None):
    # type: (int, Optional[int]) -> PowerCommand
    """ Gets the meter id from a P1 concentrator """
    if version == P1_CONCENTRATOR:
        if meter_type not in (1, 2):
            raise ValueError('Unknown meter type')
        return PowerCommand('G', 'M{0}\x00'.format(meter_type), '', '224s', module_type=PowerModuleType.C)
    raise UnsupportedException()


def get_timestamp_p1(version):
    # type: (int) -> PowerCommand
    """ Gets the timestamp from a P1 concentrator """
    if version == P1_CONCENTRATOR:
        return PowerCommand('G', 'TS\x00', '', '104s', module_type=PowerModuleType.C)
    raise UnsupportedException()


def get_gas_consumption_p1(version):
    # type: (int) -> PowerCommand
    """ Gets the gas consumption from a P1 concentrator """
    if version == P1_CONCENTRATOR:
        return PowerCommand('G', 'cG\x00', '', '112s', module_type=PowerModuleType.C)
    raise UnsupportedException()


def get_consumption_tariff_p1(version, tariff_type=None):
    # type: (int, Optional[int]) -> PowerCommand
    """ Gets the electricity consumption tariff from a P1 concentrator """
    if version == P1_CONCENTRATOR:
        if tariff_type not in (1, 2):
            raise ValueError('Unknown tariff type')
        return PowerCommand('G', 'c{0}\x00'.format(tariff_type), '', '112s', module_type=PowerModuleType.C)
    raise UnsupportedException()


def get_injection_tariff_p1(version, tariff_type=None):
    # type: (int, Optional[int]) -> PowerCommand
    """ Gets the injection tariff from a P1 concentrator """
    if version == P1_CONCENTRATOR:
        if tariff_type not in (1, 2):
            raise ValueError('Unknown tariff type')
        return PowerCommand('G', 'i{0}\x00'.format(tariff_type), '', '112s', module_type=PowerModuleType.C)
    raise UnsupportedException()


def get_tariff_indicator_p1(version):
    # type: (int) -> PowerCommand
    """ Gets the tariff indicator from a P1 concentrator """
    if version == P1_CONCENTRATOR:
        return PowerCommand('G', 'ti\x00', '', '32s', module_type=PowerModuleType.C)
    raise UnsupportedException()


def get_voltage(version, phase=None):
    # type: (int, Optional[int]) -> PowerCommand
    """
    Get the voltage of a power module (in V)
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    :param phase: Phase to read
    """
    if version in [POWER_MODULE, ENERGY_MODULE]:
        if phase is not None:
            raise ValueError('A phase is not supported')
        if version == POWER_MODULE:
            return PowerCommand('G', 'VOL', '', 'f')
        else:
            return PowerCommand('G', 'VOL', '', '12f')
    if version == P1_CONCENTRATOR:
        if phase is None:
            raise ValueError('A phase is required')
        return PowerCommand('G', 'V{0}\x00'.format(phase), '', '56s', module_type=PowerModuleType.C)
    raise UnsupportedException()


def get_frequency(version):
    # type: (int) -> PowerCommand
    """
    Get the frequency of a power module (in Hz)
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE:
        return PowerCommand('G', 'FRE', '', 'f')
    if version == ENERGY_MODULE:
        return PowerCommand('G', 'FRE', '', '12f')
    raise UnsupportedException()


def get_current(version, phase=None):
    # type: (int, Optional[int]) -> PowerCommand
    """
    Get the current of a power module (12x in A)
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    :param phase: Phase to read
    """
    if version in [POWER_MODULE, ENERGY_MODULE]:
        if phase is not None:
            raise ValueError('A phase is not supported')
        if version == POWER_MODULE:
            return PowerCommand('G', 'CUR', '', '8f')
        else:
            return PowerCommand('G', 'CUR', '', '12f')
    if version == P1_CONCENTRATOR:
        if phase is None:
            raise ValueError('A phase is required')
        return PowerCommand('G', 'C{0}\x00'.format(phase), '', '40s', module_type=PowerModuleType.C)
    raise UnsupportedException()


def get_power(version):
    # type: (int) -> PowerCommand
    """
    Get the power of a power module (12x in W)
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE:
        return PowerCommand('G', 'POW', '', '8f')
    if version == ENERGY_MODULE:
        return PowerCommand('G', 'POW', '', '12f')
    raise UnsupportedException()


def get_delivered_power(version):
    # type: (int) -> PowerCommand
    """ Gets the delivered power of a P1 concentrator """
    if version == P1_CONCENTRATOR:
        return PowerCommand('G', 'PD\x00', '', '72s', module_type=PowerModuleType.C)
    raise UnsupportedException()


def get_received_power(version):
    # type: (int) -> PowerCommand
    """ Gets the reveived power of a P1 concentrator """
    if version == P1_CONCENTRATOR:
        return PowerCommand('G', 'PR\x00', '', '72s', module_type=PowerModuleType.C)
    raise UnsupportedException()


def get_normal_energy(version):
    # type: (int) -> PowerCommand
    """
    Get the total energy measured by the power module (12x in Wh)
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == ENERGY_MODULE:
        return PowerCommand('G', 'ENE', '', '12L')
    raise UnsupportedException()


def get_day_energy(version):
    # type: (int) -> PowerCommand
    """
    Get the energy measured during the day by the power module (12x in Wh)
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE:
        return PowerCommand('G', 'EDA', '', '8L')
    if version == ENERGY_MODULE:
        return PowerCommand('G', 'EDA', '', '12L')
    if version == P1_CONCENTRATOR:
        return PowerCommand('G', 'c1\x00', '', '112s', module_type=PowerModuleType.C)
    raise UnsupportedException()


def get_night_energy(version):
    # type: (int) -> PowerCommand
    """
    Get the energy measured during the night by the power module (12x in Wh)
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE:
        return PowerCommand('G', 'ENI', '', '8L')
    if version == ENERGY_MODULE:
        return PowerCommand('G', 'ENI', '', '12L')
    if version == P1_CONCENTRATOR:
        return PowerCommand('G', 'c2\x00', '', '112s', module_type=PowerModuleType.C)
    raise UnsupportedException()


def set_day_night(version):
    """
    Set the power module in night (0) or day (1) mode.
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE:
        return PowerCommand('S', 'SDN', '8b', '')
    if version == ENERGY_MODULE:
        return PowerCommand('S', 'SDN', '12b', '')
    raise UnsupportedException()


def get_sensor_types(version):
    # type: (int) -> PowerCommand
    """
    Get the sensor types used on the power modules (8x sensor type).
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE:
        return PowerCommand('G', 'CSU', '', '8b')
    if version == ENERGY_MODULE:
        raise UnsupportedException("Getting sensor types is not applicable for the 12 port modules.")
    raise UnsupportedException()


def set_sensor_types(version):
    # type: (int) -> PowerCommand
    """
    Set the sensor types used on the power modules (8x sensor type).
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE:
        return PowerCommand('S', 'CSU', '8b', '')
    if version == ENERGY_MODULE:
        raise UnsupportedException("Setting sensor types is not applicable for the 12 port modules.")
    raise UnsupportedException()


def set_current_clamp_factor(version):
    # type: (int) -> PowerCommand
    """
    Sets the current clamp factor.
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE:
        raise UnsupportedException("Setting clamp factor is not applicable for the 8 port modules.")
    if version == ENERGY_MODULE:
        return PowerCommand('S', 'CCF', '12f', '')
    raise UnsupportedException()


def set_current_inverse(version):
    # type: (int) -> PowerCommand
    """
    Sets the current inverse.
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE:
        raise UnsupportedException("Setting current inverse is not applicable for the 8 port modules.")
    if version == ENERGY_MODULE:
        return PowerCommand('S', 'SCI', '=12B', '')
    raise UnsupportedException()


# Below are the more advanced function (12p module only)

def get_voltage_sample_time(version):
    # type: (int) -> PowerCommand
    """
    Gets a voltage sample (time - oscilloscope view)
    :param version: power api version
    """
    if version == ENERGY_MODULE:
        return PowerCommand('G', 'VST', '2b', '50f')
    if version == POWER_MODULE:
        raise UnsupportedException("Getting a voltage sample (time) is not applicable for the 8 port modules.")
    raise UnsupportedException()


def get_current_sample_time(version):
    # type: (int) -> PowerCommand
    """
    Gets a current sample (time - oscilloscope view)
    :param version: power api version
    """
    if version == ENERGY_MODULE:
        return PowerCommand('G', 'CST', '2b', '50f')
    if version == POWER_MODULE:
        raise UnsupportedException("Getting a current sample (time) is not applicable for the 8 port modules.")
    raise UnsupportedException()


def get_voltage_sample_frequency(version):
    # type: (int) -> PowerCommand
    """
    Gets a voltage sample (frequency)
    :param version: power api version
    """
    if version == ENERGY_MODULE:
        return PowerCommand('G', 'VSF', '2b', '40f')
    if version == POWER_MODULE:
        raise UnsupportedException("Getting a voltage sample (frequency) is not applicable for the 8 port modules.")
    raise UnsupportedException()


def get_current_sample_frequency(version):
    # type: (int) -> PowerCommand
    """
    Gets a current sample (frequency)
    :param version: power api version
    """
    if version == ENERGY_MODULE:
        return PowerCommand('G', 'CSF', '2b', '40f')
    if version == POWER_MODULE:
        raise UnsupportedException("Getting a current sample (frequency) is not applicable for the 8 port modules.")
    raise UnsupportedException()


def read_eeprom(version, length):
    # type: (int, int) -> PowerCommand
    """
    Reads data from the eeprom
    :param version: power api version
    :param length: Amount of bytes to be read - must be equal to the actual length argument
    """
    if version == ENERGY_MODULE:
        return PowerCommand('G', 'EEP', '2H', '{0}B'.format(length))
    if version == POWER_MODULE:
        raise UnsupportedException("Reading eeprom is not possible for the 8 port modules.")
    raise UnsupportedException()


def write_eeprom(version, length):
    # type: (int, int) -> PowerCommand
    """
    Write data to the eeprom
    :param version: power api version
    :param length: Amount of bytes to be read - must be equal to the actual amount of bytes written
    """
    if version == ENERGY_MODULE:
        return PowerCommand('S', 'EEP', '1H{0}B'.format(length), '')
    if version == POWER_MODULE:
        raise UnsupportedException("Writing eeprom is not possible for the 8 port modules.")
    raise UnsupportedException()


# Below are the address mode functions.

def set_addressmode(version):
    # type: (int) -> PowerCommand
    """ Set the address mode of the power module, 1 = address mode, 0 = normal mode """
    if version == P1_CONCENTRATOR:
        return PowerCommand('S', 'AGT', 'b', '', module_type=PowerModuleType.C)
    return PowerCommand('S', 'AGT', 'b', '')


def want_an_address(version):
    # type: (int) -> PowerCommand
    """ The Want An Address command, send by the power modules in address mode. """
    if version == POWER_MODULE:
        return PowerCommand('S', 'WAA', '', '')
    if version == ENERGY_MODULE:
        return PowerCommand('S', 'WAD', '', '')
    if version == P1_CONCENTRATOR:
        return PowerCommand('S', 'WAD', '', '', module_type=PowerModuleType.C)
    raise UnsupportedException()


def set_address(version):
    # type: (int) -> PowerCommand
    """ Reply on want_an_address, setting a new address for the power module. """
    if version == P1_CONCENTRATOR:
        return PowerCommand('S', 'SAD', 'b', '', module_type=PowerModuleType.C)
    return PowerCommand('S', 'SAD', 'b', '')


def set_voltage():
    # type: () -> PowerCommand
    """ Calibrate the voltage of the power module. """
    return PowerCommand('S', 'SVO', 'f', '')


def set_current():
    # type: () -> PowerCommand
    """ Calibrate the voltage of the power module. """
    return PowerCommand('S', 'SCU', 'f', '')


# Below are the function to reset the kwh counters

def reset_normal_energy(version):
    # type: (int) -> PowerCommand
    """
    Reset the total energy measured by the power module.
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE:
        return PowerCommand('S', 'ENE', '9B', '')
    if version == ENERGY_MODULE:
        return PowerCommand('S', 'ENE', 'B12L', '')
    raise UnsupportedException()


def reset_day_energy(version):
    # type: (int) -> PowerCommand
    """
    Reset the energy measured during the day by the power module.
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE:
        return PowerCommand('S', 'EDA', '9B', '')
    if version == ENERGY_MODULE:
        return PowerCommand('S', 'EDA', 'B12L', '')
    raise UnsupportedException()


def reset_night_energy(version):
    # type: (int) -> PowerCommand
    """
    Reset the energy measured during the night by the power module.
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE:
        return PowerCommand('S', 'ENI', '9B', '')
    if version == ENERGY_MODULE:
        return PowerCommand('S', 'ENI', 'B12L', '')
    raise UnsupportedException()


# Below are the bootloader functions

def bootloader_goto(version):
    # type: (int) -> PowerCommand
    """ Go to bootloader and wait for a number of seconds (b parameter) """
    if version == P1_CONCENTRATOR:
        return PowerCommand('S', 'RES', 'B', '', module_type=PowerModuleType.C)
    return PowerCommand('S', 'BGT', 'B', '')


def bootloader_read_id():
    # type: () -> PowerCommand
    """ Get the device id """
    return PowerCommand('G', 'BRI', '', '8B')


def bootloader_write_code(version):
    # type: (int) -> PowerCommand
    """
    Write code
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE:
        return PowerCommand('S', 'BWC', '195B', '')
    if version == ENERGY_MODULE:
        return PowerCommand('S', 'BWC', '132B', '')
    raise UnsupportedException()


def bootloader_erase_code():
    # type: () -> PowerCommand
    """ Erase the code on a given page. """
    return PowerCommand('S', 'BEC', 'H', '')


def bootloader_write_configuration():
    # type: () -> PowerCommand
    """ Write configuration """
    return PowerCommand('S', 'BWF', '24B', '')


def bootloader_jump_application():
    # type: () -> PowerCommand
    """ Go from bootloader to applications """
    return PowerCommand('S', 'BJA', '', '')


def get_version(version):
    # type: (int) -> PowerCommand
    """ Get the current version of the power module firmware """
    if version == P1_CONCENTRATOR:
        return PowerCommand('G', 'FVE', '', '4B', module_type=PowerModuleType.C)
    return PowerCommand('G', 'FIV', '', '16s')


# Below are the debug functions

def raw_command(mode, command, num_bytes):
    # type: (str, str, int) -> PowerCommand
    """ Create a PowerCommand for debugging purposes. """
    return PowerCommand(mode, command, '%dB' % num_bytes, None)
