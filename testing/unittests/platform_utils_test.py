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
from __future__ import absolute_import

import sys
before_imports = sys.modules

import mock
import unittest
import subprocess


from platform_utils import System, Platform, Hardware



class PlatformUtilsTest(unittest.TestCase):

    def test_import_dependencies(self):
        """ Test if there are no imports in platform utils that are not built-in packages """
        try:
            import os
            import subprocess

            platform_utils_file_location = os.path.join(os.path.abspath(__file__), '../../../src')
            platform_utils_file_location = os.path.abspath(platform_utils_file_location)  # This will clear all the ../

            py_cmd = 'print("Running test code");' \
                     'import os;' \
                     'os.chdir("{0}");' \
                     'print(os.getcwd());' \
                     'import sys;' \
                     'sys.path = [x for x in sys.path if "site-packages" not in x]; ' \
                     'print(sys.path); ' \
                     'import platform_utils' \
                     .format(platform_utils_file_location)

            cmd = ['python', '-c', py_cmd]
            ret = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            exit_code = ret.returncode
            self.assertEqual(0, exit_code)
        except Exception as e:
            self.fail('Could not import the platform utils. Make sure there are no dependencies in the platform'
                      ' utils script other than the default python packages. Error: {}'.format(e))



    def test_get_ip_address(self):
        expected_ip_address = "192.168.0.126"

        platform_specifics = {'ANGSTROM': {'operating_system': {'ID': 'angstrom'},
                                           'ifconfig_output': ANGSTROM_IFCONFIG_OUTPUT},
                              'DEBIAN': {'operating_system': {'ID': 'debian'},
                                         'ifconfig_output': DEBIAN_IFCONFIG_OUTPUT}}
        for platform, details in platform_specifics.items():
            with mock.patch.object(subprocess, 'check_output', return_value=details['ifconfig_output']),\
                 mock.patch.object(System, 'get_operating_system', return_value=details['operating_system']):
                ip_address = System.get_ip_address()
                self.assertEqual(expected_ip_address, ip_address)


DEBIAN_IFCONFIG_OUTPUT = """eth0: flags=-28605<UP,BROADCAST,RUNNING,MULTICAST,DYNAMIC>  mtu 1500
        inet 192.168.0.126  netmask 255.255.255.0  broadcast 10.26.12.255
        inet6 fe80::f245:daff:fe81:5549  prefixlen 64  scopeid 0x20<link>
        inet6 fd6c:34ed:1733:1:f245:daff:fe81:5549  prefixlen 64  scopeid 0x0<global>
        inet6 fdc1:bf06:4637:1:f245:daff:fe81:5549  prefixlen 64  scopeid 0x0<global>
        ether 6c:ec:eb:b9:fc:c9  txqueuelen 1000  (Ethernet)
        RX packets 514006  bytes 129201839 (123.2 MiB)
        RX errors 0  dropped 86615  overruns 0  frame 0
        TX packets 393427  bytes 75373897 (71.8 MiB)
        TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0
        device interrupt 50

lo: flags=73<UP,LOOPBACK,RUNNING>  mtu 65536
        inet 127.0.0.1  netmask 255.0.0.0
        inet6 ::1  prefixlen 128  scopeid 0x10<host>
        loop  txqueuelen 1000  (Local Loopback)
        RX packets 583647  bytes 60356828 (57.5 MiB)
        RX errors 0  dropped 0  overruns 0  frame 0
        TX packets 583647  bytes 60356828 (57.5 MiB)
        TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0

tun0: flags=4305<UP,POINTOPOINT,RUNNING,NOARP,MULTICAST>  mtu 1500
        inet 10.37.0.26  netmask 255.255.255.255  destination 10.37.0.25
        inet6 fe80::3a07:3147:cc6d:f341  prefixlen 64  scopeid 0x20<link>
        unspec 00-00-00-00-00-00-00-00-00-00-00-00-00-00-00-00  txqueuelen 100  (UNSPEC)
        RX packets 1730  bytes 156952 (153.2 KiB)
        RX errors 0  dropped 0  overruns 0  frame 0
        TX packets 1612  bytes 394218 (384.9 KiB)
        TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0
"""

ANGSTROM_IFCONFIG_OUTPUT = """eth0      Link encap:Ethernet  HWaddr 6C:EC:EB:B9:FC:C9
          inet addr:192.168.0.126  Bcast:192.168.0.255  Mask:255.255.255.0
          inet6 addr: 2a02:1812:250f:d100:6eec:ebff:feb9:fcc9/64 Scope:Global
          inet6 addr: fe80::6eec:ebff:feb9:fcc9/64 Scope:Link
          UP BROADCAST RUNNING MULTICAST  MTU:1500  Metric:1
          RX packets:21032607 errors:0 dropped:1732655 overruns:0 frame:0
          TX packets:14988679 errors:0 dropped:0 overruns:0 carrier:0
          collisions:0 txqueuelen:1000
          RX bytes:1481173618 (1.3 GiB)  TX bytes:3449848196 (3.2 GiB)
          Interrupt:56
lo        Link encap:Local Loopback
          inet addr:127.0.0.1  Mask:255.0.0.0
          inet6 addr: ::1/128 Scope:Host
          UP LOOPBACK RUNNING  MTU:65536  Metric:1
          RX packets:29686303 errors:0 dropped:0 overruns:0 frame:0
          TX packets:29686303 errors:0 dropped:0 overruns:0 carrier:0
          collisions:0 txqueuelen:0
          RX bytes:6948795341 (6.4 GiB)  TX bytes:6948795341 (6.4 GiB)
tun0      Link encap:UNSPEC  HWaddr 00-00-00-00-00-00-00-00-00-00-00-00-00-00-00-00
          inet addr:10.37.2.174  P-t-P:10.37.2.173  Mask:255.255.255.255
          UP POINTOPOINT RUNNING NOARP MULTICAST  MTU:1500  Metric:1
          RX packets:17667 errors:0 dropped:0 overruns:0 frame:0
          TX packets:18180 errors:0 dropped:0 overruns:0 carrier:0
          collisions:0 txqueuelen:100
          RX bytes:2166259 (2.0 MiB)  TX bytes:4224708 (4.0 MiB)
"""
