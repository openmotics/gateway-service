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
Contains the definition of the RS485 API
"""

from __future__ import absolute_import
from master.core.rs485_command import RS485CommandSpec, Instruction
from master.core.fields import ByteField, VersionField


class RS485API(object):

    @staticmethod
    def get_firmware_version():
        """ Gets a slave firmware version """
        return RS485CommandSpec(instruction=Instruction(instruction='FV', padding=9),
                                response_fields=[ByteField('error'), ByteField('hardware_version'),
                                                 VersionField('version'), ByteField('status')])

    @staticmethod
    def goto_bootloader():
        """ Instructs a slave to go to bootloader """
        return RS485CommandSpec(instruction=Instruction(instruction='FR', padding=8),
                                request_fields=[ByteField('timeout')],
                                response_fields=[ByteField('error')])

    @staticmethod
    def goto_application():
        """ Instructs a slave to go to application """
        return RS485CommandSpec(instruction=Instruction(instruction='FG', padding=9),
                                response_fields=[ByteField('error')])
