#!/usr/bin/env python2

import argparse
import collections
import os
import re

from intelhex import IntelHex


SUPPORTED_MODULES = ['RY', 'ZL', 'CL', 'IT', 'MN']
FILE_P = re.compile(r'^OMF(?P<type>\w\w)_'
                    r'(?P<firmware>\d+\.\d+\.\d+)_'
                    r'B(?P<bootloader>\d+\.\d+)\.hex$')
SERIAL_P = re.compile(r'^(?P<year>\d\d)'
                      r'(?P<month>\d\d)'
                      r'(?P<day>\d\d)'
                      r'(?P<company>\d)'
                      r'(?P<number>\d\d\d\d\d)$')


SerialNumber = collections.namedtuple(
    'SerialNumber', ['year', 'month', 'day', 'company', 'number'])


def get_module_from_file_name(file_name):
    file_m = FILE_P.match(file_name)
    if file_m:
        module_type = file_m.group('type')
        if module_type not in SUPPORTED_MODULES:
            raise ValueError('Unsupported module type %s' % module_type)
    else:
        raise ValueError('Cannot infer the module type from file name')
    return module_type


def parse_serial_number(serial_number):
    serial_m = SERIAL_P.match(serial_number)
    if not serial_m:
        return ValueError('Serial number not correctly formatted')
    return SerialNumber(*(int(g) for g in serial_m.groups()))


def create_out_file(in_file, serial_number):
    file_name = os.path.basename(in_file)
    if '.' in file_name:
        base, _, ext = file_name.rpartition('.')
        new_file_name = '%s_%s.%s' % (base, serial_number, ext)
    else:
        new_file_name = '%s_%s' % (file_name, serial_number)
    return os.path.join(os.path.dirname(in_file), new_file_name)


def add_serial_to_hex(module_type, hex_file, serial_number, hardware_revision=None):
    if module_type == 'MN':
        add_serial_to_ucan_hex(hex_file, serial_number, hardware_revision)
    else:
        add_serial_to_din_hex(hex_file, serial_number)


def add_serial_to_din_hex(hex_file, serial_number):
    # See https://wiki.openmotics.com/index.php/Test_System#Serial_number_.26_hardware_revision_location_in_EEPROM
    hex_file[0xF000F0] = serial_number.year & 0xFF
    hex_file[0xF000F1] = serial_number.month & 0xFF
    hex_file[0xF000F2] = serial_number.day & 0xFF
    hex_file[0xF000F3] = serial_number.company & 0xFF
    hex_file[0xF000F4] = (serial_number.number & 0xFF00) >> 8  # MSB
    hex_file[0xF000F5] = serial_number.number & 0xFF  # LSB
    hex_file[0xF000F6] = 0  # Number of errors during testing


def add_serial_to_ucan_hex(hex_file, serial_number, hardware_revision):
    # See https://wiki.openmotics.com/index.php/Test_System#Serial_number_.26_hardware_revision_location_in_EEPROM
    hex_file[0xF0001E] = ord(hardware_revision.upper())
    hex_file[0xF0038A] = serial_number.year & 0xFF
    hex_file[0xF00389] = serial_number.month & 0xFF
    hex_file[0xF00388] = serial_number.day & 0xFF
    hex_file[0xF00384] = serial_number.company & 0xFF
    hex_file[0xF00386] = (serial_number.number & 0xFF00) >> 8  # MSB
    hex_file[0xF00387] = serial_number.number & 0xFF  # LSB
    hex_file[0xF0038B] = 0  # Number of errors during testing
    hex_file[0xF00385] = 0  # No idea what is gap is, but 0 seems okay


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('hex', help='The original .hex file')
    parser.add_argument('serial', help='Serial number to add')
    parser.add_argument('--type', choices=SUPPORTED_MODULES,
                        help='Module type (default: inferred from file name)',
                        default=None)
    parser.add_argument('--out',
                        help='Output file name (default: add S/N before extension')
    parser.add_argument('--hw',
                        help='Hardware revision (for micro CAN)')
    args = parser.parse_args()

    module_type = args.type
    if not module_type:
        file_name = os.path.basename(args.hex)
        module_type = get_module_from_file_name(file_name)

    serial_number = parse_serial_number(args.serial)

    out_file = args.out
    if not out_file:
        out_file = create_out_file(args.hex, args.serial)

    hex_file = IntelHex(args.hex)
    add_serial_to_hex(module_type, hex_file, serial_number, args.hw)
    hex_file.write_hex_file(out_file)


if __name__ == '__main__':
    main()
