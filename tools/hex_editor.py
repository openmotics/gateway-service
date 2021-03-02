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
import os
import sys
from intelhex import IntelHex


def edit(source_filename, destination_filename):
    hexfile = IntelHex(source_filename)
    print('Manually edit some bytes in a hexfile')
    print('You will be asked for a address/value pair to change. All data must be in hex.')
    print('Example: `40 FF` will save `0xFF` at address `0x40`.')
    print('Enter `stop` to stop changing bytes and save the file.')
    try:
        while True:
            answer = raw_input('Enter data or stop: ')
            if answer == 'stop':
                break
            hex_address, hex_value = answer.split(' ')
            hexfile[int(hex_address, 16)] = int(hex_value, 16)
        hexfile.write_hex_file(destination_filename)
    except KeyboardInterrupt:
        print('Aborting')


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print('Usage: ./hex_editor.py source.hex changed.hex')
        sys.exit(1)
    filename_1 = sys.argv[1]
    if not os.path.exists(filename_1):
        print('File {0} does not exist'.format(filename_1))
        sys.exit(1)
    filename_2 = sys.argv[2]

    edit(filename_1, filename_2)
