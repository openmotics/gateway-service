#!/bin/python2
# Copyright (C) 2021 OpenMotics BV
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
import sys
from serial.serialposix import Serial


def watch(port):
    try:
        previous_output = None
        serial = Serial(port, 115200, timeout=0.5)
        _read(serial)  # Clear buffer
        count = 0
        while True:
            count += 1
            serial.write('output list\r\n')
            output = _read(serial).strip()
            if output != previous_output:
                _print_diff(previous_output if previous_output is not None else output,
                            output)
                previous_output = output
                sys.stdout.write('Count: {0:04d}'.format(count))
            sys.stdout.write('\rCount: {0:04d}'.format(count))
            sys.stdout.flush()
    except KeyboardInterrupt:
        print('Exit')


def _print_diff(a_string, b_string):
    output = ''
    color_started = False
    for i in range(max(len(a_string), len(b_string))):
        a = a_string[i] if i < len(a_string) else '?'
        b = b_string[i] if i < len(b_string) else '?'
        if a != b:
            if color_started is False:
                output += '\033[101m'
                color_started = True
        else:
            if color_started is True:
                output += '\033[0m'
                color_started = False
        output += b
    output += '\033[0m'
    sys.stdout.write('\n\n{0}\n\n'.format(output))
    sys.stdout.flush()


def _read(serial):
    buffer = ''
    new_data = serial.read(1)
    while len(new_data) > 0:
        buffer += new_data
        if buffer.endswith('OK'):
            return buffer
        new_data = serial.read(1)
    return buffer


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print('Validates correct communication with the Brain using CLI (error list)')
        print('Usage: ./validate_cli_serial.py <port>')
        print('Port is typically /dev/ttyO2')
        sys.exit(1)
    watch(sys.argv[1])
