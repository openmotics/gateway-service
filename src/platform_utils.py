# Copyright (C) 2018 OpenMotics BV
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
""""
The platform_utils module contains various classes helping with Hardware, System and Platform abstraction
"""
from __future__ import absolute_import
import logging
import os
import subprocess
import sys
import constants
import time

if False:  # MYPY
    from typing import Union, Dict, List, Tuple

logger = logging.getLogger(__name__)


class Hardware(object):
    """
    Abstracts the hardware related functions
    """
    class BoardType(object):
        BB = 'BB'
        BBB = 'BBB'
        BBGW = 'BBGW'
        ESAFE = 'ESAFE'

    BoardTypes = [BoardType.BB, BoardType.BBB, BoardType.BBGW]

    class GPIO_DIRECTION(object):
        IN = 'in'
        OUT = 'out'

    GPIO_BASE_PATH = '/sys/class/gpio/gpio{0}'
    GPIO_EXPORT_PATH = '/sys/class/gpio/export'
    GPIO_DIRECTION_PATH = '{0}/direction'.format(GPIO_BASE_PATH)
    GPIO_VALUE_PATH = '{0}/value'.format(GPIO_BASE_PATH)

    class CoreGPIO(object):
        RS232_MODE = (77, False)
        P1_DATA_ENABLE = (113, False)
        P1_CABLE_CONNECTED = (115, False)
        MASTER_POWER = (49, True)

    class ClassicGPIO(object):
        pass

    # eMMC registers
    EXT_CSD_DEVICE_LIFE_TIME_EST_TYP_B = 269
    EXT_CSD_DEVICE_LIFE_TIME_EST_TYP_A = 268
    EXT_CSD_PRE_EOL_INFO = 267

    @staticmethod
    def read_mmc_ext_csd():
        registers = {
            'life_time_est_typ_b': Hardware.EXT_CSD_DEVICE_LIFE_TIME_EST_TYP_B,
            'life_time_est_typ_a': Hardware.EXT_CSD_DEVICE_LIFE_TIME_EST_TYP_A,
            'eol_info': Hardware.EXT_CSD_PRE_EOL_INFO,
        }
        with open('/sys/kernel/debug/mmc1/mmc1:0001/ext_csd') as fd:
            ecsd = fd.read()

        ecsd_info = {}
        # NOTE: this only works for fields with length 1
        for reg, i in registers.items():
            pos = i * 2
            ecsd_info[reg] = int(ecsd[pos:pos + 2], 16)
        return ecsd_info

    @staticmethod
    def get_board_type():
        # type: () -> Union[str, None]
        try:
            with open('/proc/device-tree/model', 'r') as mfh:
                board_type = mfh.read().strip('\x00').replace(' ', '_')
                if board_type in ['TI_AM335x_BeagleBone', 'TI_AM335x_BeagleBone_Black']:
                    return Hardware.BoardType.BBB
                if board_type in ['TI_AM335x_BeagleBone_Green_Wireless']:
                    return Hardware.BoardType.BBGW
                if board_type in ['TI_AM335x_esafe_Custom']:
                    return Hardware.BoardType.ESAFE
        except IOError:
            pass
        try:
            with open('/proc/meminfo', 'r') as memfh:
                mem_total = memfh.readline()
                if '254228 kB' in mem_total:
                    return Hardware.BoardType.BB
                if '510716 kB' in mem_total:
                    return Hardware.BoardType.BBB
        except IOError:
            pass
        logger.warning('could not detect board type, unknown')
        return None  # Unknown

    @staticmethod
    def get_board_serial_number():
        # type: () -> Union[str, None]
        serial_number = None
        try:
            with open('/sys/bus/i2c/devices/0-0050/eeprom') as fd:
                serial_pos, serial_length = 16, 12
                fd.seek(serial_pos)
                serial_number = str(fd.read(serial_length))
        except Exception:
            logger.error('Unable to read board serial number')
        return serial_number

    @staticmethod
    def get_main_interface():
        board_type = Hardware.get_board_type()
        if board_type in [Hardware.BoardType.BB, Hardware.BoardType.BBB, Hardware.BoardType.ESAFE]:
            return 'eth0'
        if board_type == Hardware.BoardType.BBGW:
            return 'wlan0'
        logger.warning('Could not detect local interface. Fallback: lo')
        return 'lo'

    @staticmethod
    def get_mac_address():
        # type: () -> Union[str, None]
        """ Get the main interface mac address """
        interface = Hardware.get_main_interface()
        try:
            # This works both on Angstrom and Debian
            with open('/sys/class/net/{0}/address'.format(interface)) as mac_address:
                return mac_address.read().strip().upper()
        except Exception:
            return None

    @staticmethod
    def set_gpio_direction(gpio, direction):  # type: (Tuple[int, bool], str) -> None
        pin, inverted = gpio
        if not os.path.exists(Hardware.GPIO_BASE_PATH.format(pin)):
            with open(Hardware.GPIO_EXPORT_PATH, 'w') as gpio_file:
                gpio_file.write(str(pin))
        with open(Hardware.GPIO_DIRECTION_PATH.format(pin), 'w') as gpio_file:
            gpio_file.write(direction)

    @staticmethod
    def set_gpio(gpio, value):  # type: (Tuple[int, bool], bool) -> None
        pin, inverted = gpio
        Hardware.set_gpio_direction(gpio=gpio,
                                    direction=Hardware.GPIO_DIRECTION.OUT)
        if inverted:
            value = not value
        with open(Hardware.GPIO_VALUE_PATH.format(pin), 'w') as gpio_file:
            gpio_file.write('1' if value else '0')

    @staticmethod
    def cycle_gpio(gpio, cycle):  # type: (Tuple[int, bool], List[Union[bool, float]]) -> None
        """
        Will cycle a given GPIO through a certain pattern `cycle`. This pattern
        is a list of booleans and floats where every booilean will result in setting
        the GPIO to this state, and every flow will wait for that amount of seconds.
        Example:
        > [False, 2.0, True]  # This will immediately turn the GPIO off, wait 2 seconds,
        >                     # and turn it on again.
        :param gpio: The GPIO pin
        :param cycle: The cycle to follow
        """
        pin, inverted = gpio
        Hardware.set_gpio_direction(gpio=gpio,
                                    direction=Hardware.GPIO_DIRECTION.OUT)
        for item in cycle:
            if isinstance(item, bool):
                with open(Hardware.GPIO_VALUE_PATH.format(pin), 'w') as gpio_file:
                    value = item
                    if inverted:
                        value = not value
                    gpio_file.write('1' if value else '0')
            elif isinstance(item, float):
                time.sleep(item)
            else:
                raise ValueError('Unexpected {0} in cycle {1}'.format(item, cycle))

    @staticmethod
    def enable_extension_rs485_port():
        current_platform = Platform.get_platform()
        if current_platform not in Platform.CoreTypes:
            raise RuntimeError('Platform {0} does not support the extension RS485 port')
        Hardware.set_gpio(Hardware.CoreGPIO.RS232_MODE, False)


class System(object):
    """
    Abstracts the system related functions
    """

    SERVICES = ('vpn_service', 'openmotics')

    SYSTEMD_UNIT_MAP = {'openmotics': 'openmotics-api.service',
                        'vpn_service': 'openmotics-vpn.service'}
    # runit action map to make sure the executable will be stopped,
    # otherwise runit will return timeout, but not have killed the app
    RUNIT_ACTION_MAP = {'status': 'status',
                        'stop': 'force-stop',
                        'restart': 'force-restart'}

    class OS(object):
        ANGSTROM = 'angstrom'
        DEBIAN = 'debian'
        BUILDROOT = 'buildroot'

    @staticmethod
    def restart_service(service):
        # type: (str) -> None
        System.run_service_action('restart', service)

    @staticmethod
    def run_service_action(action, service):
        # type: (str, str) -> subprocess.Popen
        unit_name = System.SYSTEMD_UNIT_MAP.get(service, service)
        is_systemd = False
        is_supervisor = False
        is_runit = False
        try:
            subprocess.check_output(['systemctl', 'is-enabled', unit_name])
            is_systemd = True
        except subprocess.CalledProcessError:
            is_systemd = False
        except Exception:  # Python 3 error (FileNotFoundErr) but is not known in python 2...
            is_systemd = False

        try:
            subprocess.check_output(['supervisorctl', 'status', service])
            is_supervisor = True
        except subprocess.CalledProcessError:
            is_supervisor = False
        except Exception:  # Python 3 error (FileNotFoundErr) but is not known in python 2...
            is_supervisor = False

        try:
            runit_path = constants.get_runit_service_folder()
            subprocess.check_output(['sv', 'status', os.path.join(runit_path, service)])
            is_runit = True
        except subprocess.CalledProcessError:
            is_runit = False
        except Exception:  # Python 3 error (FileNotFoundErr) but is not known in python 2...
            is_runit = False

        if is_systemd:
            return subprocess.Popen(['systemctl', action, '--no-pager', unit_name],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    close_fds=True)
        elif is_supervisor:
            return subprocess.Popen(['supervisorctl', action, service],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    close_fds=True)
        elif is_runit:
            runit_path = constants.get_runit_service_folder()
            service_str = os.path.join(runit_path, service)
            return subprocess.Popen(['sv', action, service_str],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    close_fds=True)
        else:
            raise RuntimeError('Could not find the appropriate service manager to run the service action command')

    @staticmethod
    def get_operating_system():
        # type: () -> Dict[str, str]
        operating_system = {}
        try:
            with open('/etc/os-release', 'r') as osfh:
                lines = osfh.readlines()
                for line in lines:
                    k, v = line.strip().split('=')
                    operating_system[k] = v
            operating_system['ID'] = operating_system['ID'].lower()
        except IOError:
            logger.warning('could not detect operating system, unknown')
        return operating_system

    @staticmethod
    def get_ip_address():
        """ Get the local ip address. """
        interface = Hardware.get_main_interface()
        operating_system = System.get_operating_system()
        try:
            lines = subprocess.check_output('ifconfig {0}'.format(interface), shell=True)
            # In python3, lines is a bytes array variable, not a string. -> decoding it into a string
            if not isinstance(lines, str):
                lines = lines.decode('utf-8')
            if operating_system['ID'] == System.OS.ANGSTROM:
                return lines.split('\n')[1].strip().split(' ')[1].split(':')[1]
            elif operating_system['ID'] == System.OS.DEBIAN:
                return lines.split('\n')[1].strip().split(' ')[1]
            elif operating_system['ID'] == System.OS.BUILDROOT:
                return lines.split('\n')[1].strip().split(' ')[1].replace('addr:','')  # The buildroot OS prefixes addresses with 'addr'
            else:
                return
        except Exception:
            return

    @staticmethod
    def get_vpn_service():
        return 'openvpn.service' if System.get_operating_system().get('ID') == System.OS.ANGSTROM else 'openvpn-client@omcloud'

    @staticmethod
    def _use_pyopenssl():
        return System.get_operating_system().get('ID') == System.OS.ANGSTROM

    @staticmethod
    def get_ssl_socket(sock, private_key_filename, certificate_filename):
        if System._use_pyopenssl():
            from OpenSSL import SSL
            context = SSL.Context(SSL.SSLv23_METHOD)
            context.use_privatekey_file(private_key_filename)
            context.use_certificate_file(certificate_filename)
            return SSL.Connection(context, sock)
        import ssl
        return ssl.wrap_socket(sock,
                               keyfile=private_key_filename,
                               certfile=certificate_filename,
                               ssl_version=ssl.PROTOCOL_SSLv23,
                               do_handshake_on_connect=False,
                               suppress_ragged_eofs=False)

    @staticmethod
    def setup_cherrypy_ssl(https_server):
        if System._use_pyopenssl():
            https_server.ssl_module = 'pyopenssl'
        else:
            import ssl
            https_server.ssl_module = 'builtin'
            if sys.version_info[:3] < (3, 6, 0):
                https_server.ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)

    @staticmethod
    def handle_socket_exception(connection, exception, logger):
        if System._use_pyopenssl():
            import select
            from OpenSSL import SSL
            if isinstance(exception, SSL.SysCallError):
                if exception[0] == 11:  # Temporarily unavailable
                    # This should be ok, just wait for more data to arrive
                    return True  # continue
                if exception[0] == -1:  # Unexpected EOF
                    logger.info('Got (unexpected) EOF, aborting due to lost connection')
                    return False  # break
            elif isinstance(exception, SSL.WantReadError):
                # This should be ok, just wait for more data to arrive
                select.select([connection], [], [], 1.0)
                return True  # continue
        else:
            import select
            import ssl
            if isinstance(exception, ssl.SSLEOFError):
                logger.info('Got SSLEOFError, aborting due to lost connection')
                return False  # break
            elif isinstance(exception, ssl.SSLError):
                if 'The read operation timed out' in str(exception):
                    # Got read timeout, just wait for data to arrive
                    return True  # continue
        raise exception

    @staticmethod
    def import_libs():
        operating_system = System.get_operating_system().get('ID')
        # check if running in python 2 mode, otherwise packages should be included in the build (PyInstaller)
        if sys.version_info.major == 2:
            import site
            path = os.path.abspath(os.path.join(__file__, '../../python-deps/lib/python2.7/site-packages'))
            if os.path.exists(path):
                site.addsitedir(path)
                sys.path.remove(path)
                sys.path.insert(0, path)

        if operating_system in [System.OS.ANGSTROM, System.OS.DEBIAN]:
            path = os.path.abspath(os.path.join(__file__, '../libs/cacert.pem'))
            os.environ['REQUESTS_CA_BUNDLE'] = path


class Platform(object):
    """
    Abstracts the platform related functions
    """

    class Type(object):
        DUMMY = 'DUMMY'
        ESAFE_DUMMY = 'ESAFE_DUMMY'
        CLASSIC = 'CLASSIC'
        CORE_PLUS = 'CORE_PLUS'
        CORE = 'CORE'
        ESAFE = 'ESAFE'

    DummyTypes = [Type.DUMMY, Type.ESAFE_DUMMY]
    ClassicTypes = [Type.CLASSIC]
    CoreTypes = [Type.CORE, Type.CORE_PLUS]
    EsafeTypes = [Type.ESAFE]
    Types = DummyTypes + ClassicTypes + CoreTypes + EsafeTypes

    @staticmethod
    def get_platform():
        # type: () -> str
        from six.moves.configparser import ConfigParser
        config = ConfigParser()
        config.read(constants.get_config_file())

        if config.has_option('OpenMotics', 'platform'):
            platform = config.get('OpenMotics', 'platform')
            if platform in Platform.Types:
                return platform
        return Platform.Type.CLASSIC


    @staticmethod
    def get_registration_key():
        # type: () -> str
        from six.moves.configparser import ConfigParser
        config = ConfigParser()
        config.read(constants.get_config_file())
        return config.get('OpenMotics', 'uuid')

    @staticmethod
    def has_master_hardware():
        # type: () -> bool
        if Platform.get_platform() in [Platform.Type.DUMMY, Platform.Type.ESAFE]:
            return False
        return True

    @staticmethod
    def http_port():
        # type: () -> int
        try:
            from six.moves.configparser import ConfigParser
            config = ConfigParser()
            config.read(constants.get_config_file())
            http_port = int(config.get('OpenMotics', 'http_port'))
            if http_port is None:
                http_port = 80  # default http port
            return http_port
        except Exception:
            return 80

    @staticmethod
    def https_port():
        # type: () -> int
        try:
            from six.moves.configparser import ConfigParser
            config = ConfigParser()
            config.read(constants.get_config_file())
            https_port = int(config.get('OpenMotics', 'https_port'))
            if https_port is None:
                https_port = 433  # default https port
            return https_port
        except Exception:
            return 433
