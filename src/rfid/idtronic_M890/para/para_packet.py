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
"""
Para packet definition
"""
from functools import reduce
from operator import xor

from enum import Enum

# https://stackoverflow.com/questions/1456373/two-way-reverse-map/13276237
class TwoWayDict(dict):
    def __setitem__(self, key, value):
        # Remove any previous connections with these values
        if key in self:
            del self[key]
        if value in self:
            del self[value]
        dict.__setitem__(self, key, value)
        dict.__setitem__(self, value, key)

    def __delitem__(self, key):
        dict.__delitem__(self, self[key])
        dict.__delitem__(self, key)

    def __len__(self):
        """Returns the number of connections"""
        return dict.__len__(self) // 2

    def get_item_default(self, key, default=None):
        if key in self:
            return self[key]
        else:
            return default


class ParaPacketType(Enum):
    AutoListCard = 0x23
    I2_inventory = 0xA1
    MFCAuthenticate = 0x16
    MFCReadBlock = 0x17
    MFCWriteBlock = 0x18
    MFCActivate = 0x22
    MFCInitValue = 0x1A
    MFCUpdateValue = 0x1B
    MFCBackupValue = 0x1C
    MFCReadValue = 0x1D
    ERROR_RESPONSE = 0xF


class ParaPacketHeader(object):

    def __init__(self, data=None):
        if data is not None:
            if len(data) != 4:
                raise ValueError('para-header constructor: The value of data is not 4 bytes long')
            self.raw = data
            self.version = data[0]
            self.data_length = data[1] * 256 + data[2]
            self.command_type = data[3]
        else:
            self.raw = []
            self.version = None
            self.data_length = None
            self.command_type = None

    def is_complete(self):
        return self.version is not None and \
               self.data_length is not None and \
               self.command_type is not None

    def append_byte(self, byte):
        if isinstance(byte, bytes):
            byte = int.from_bytes(byte, "big")
        if byte > 255:
            raise Exception('Appending a byte to a para packet header cannot be bigger than 255.')
        if not self.is_complete():
            self.raw.append(byte)
            current_len = len(self.raw)
            if current_len == 1:
                self.version = self.raw[0]
                return False
            elif current_len == 2:
                # do nothing yet, data length is not complete
                return False
            elif current_len == 3:
                self.data_length = self.raw[1] * 255 + self.raw[2]
                return False
            elif current_len == 4:
                self.command_type = self.raw[3]
                return True
            else:
                raise Exception("para-header: Unknown case, should not happen, byte: {:X}, len: {}".format(byte, current_len))
        else:
            raise Exception("appending byte to header: is already full")

    def get_command_type_string(self):
        cmd_code = self.command_type
        if cmd_code in ParaPacketType:
            return ParaPacketType(cmd_code).name
        return None

    def __str__(self):
        res = "Para packet header:\n"
        res += "------------------\n"
        res += "    version: 0x{0:X} ({0})\n".format(self.version)
        res += "    data length: 0x{0:X} ({0})\n".format(self.data_length)
        res += "    command type: 0X{0:X} ({0}) = {1}\n".format(self.command_type, self.get_command_type_string())
        return res


class ParaPacket(object):
    para_error = TwoWayDict()
    for key, value in {
        "LRC_err": 0xF1,
        "NoThisCmd_err": 0xF2,
        "Set_err": 0xF3,
        "Para_err": 0xF4,
        "NoCard_err": 0xB1,
        "AntiColl_err": 0xB2,
        "Select_err": 0xB3,
        "Halt_err": 0xB4,
        "Auth_err": 0xB6,
        "Read_err": 0xB7,
        "Write_err": 0xB8,
        "ValueOp_err": 0xB9,
        "ValueBack_err": 0xBA,
        "RATS_err": 0xBC,
        "TPCL_err": 0xBE,
        "PwrUp_err": 0xD1,
        "PwrOff_err": 0xD2,
        "APDU_err": 0xD3,
        "PTS_err": 0xD4,
        "NoSlot_err": 0xD5,
        "Chack_err": 0xD6,
        "TimeoutRcv_err": 0x10,
        "BIF_LRC_err": 0x11,
        "RxBufFull_err": 0x12,
        "WrHwParam_err": 0x30,
        "ChkSmHwParam_err": 0x31,
        "HwParam_err": 0x32,
        "UnknownCmdType_err": 0x20,
        "UnknownCmd_err": 0x21,
        "ParamNotCorr_err": 0x22,
        "ISO14443AHalt_err": 0xA0,
        "ISO14443AAuth_err": 0xA1,
        "ISO14443ANotAuth_err": 0xA2,
        "ISO14443AMifare_err": 0xA3,
        "NoResponse_err": 0xE0,
        "Framing_err": 0xE1,
        "Collision_err": 0xE2,
        "Parity_err": 0xE3,
        "CRC_err": 0xE4,
        "InvalidResp_err": 0xE5,
        "SubCarrierDetection_err": 0xE6
    }.items():
        para_error[key] = value

    def __init__(self, data=None):
        if data is not None:
            self.raw = data
            self.header = ParaPacketHeader(data[0:4])
            if len(data) > 5:
                self.data = data[4:-1]
            else:
                self.data = []
            self.xor = data[-1]

        else:
            self.raw = []
            self.header = ParaPacketHeader()
            self.data = []
            self.xor = None

    def is_complete(self):
        if not self.header.is_complete():
            return False

        return self.xor is not None

    def append_byte(self, byte):
        if isinstance(byte, bytes):
            byte = int.from_bytes(byte, "big")
        if not self.is_complete():
            self.raw.append(byte)
            current_len = len(self.raw)
            if current_len <= 4:
                try:
                    self.header.append_byte(byte)
                except Exception:
                    raise Exception("Trying to add to header but full, this should not happen...")
                return False
            elif current_len >= 4 and self.header.is_complete():
                data_length = self.header.data_length
                if (current_len - 5) < data_length:  # header (4) plus xor (1)
                    self.data.append(self.raw[-1])
                    return False
                elif current_len - 5 == self.header.data_length:
                    self.xor = self.raw[-1]
                    return True
            else:
                raise Exception("para-packet: Unknown case, should not happen, byte: {}, len: {}".format(byte, current_len))
        else:
            raise Exception("appending byte: package is already full")

    def crc_check(self):
        calc_xor = reduce(xor, self.raw[:-1])
        return calc_xor == self.xor

    def append_crc_check_value(self):
        calc_xor = reduce(xor, self.raw)
        self.append_byte(calc_xor)

    def serialize(self):
        return bytearray(self.raw)

    def get_error_value(self):
        err_value = None
        if self.header.version == ParaPacketHeader.command_type['ERROR_RESPONSE']:
            err_value = self.data[0]
        return err_value

    def get_error_name(self):
        err_name = None
        err_value = self.get_error_value()
        if err_value is not None:
            err_name = ParaPacket.para_error[err_value]
        return err_name

    def data_hex(self):
        res = ', '.join(['0x{:02X}'.format(x) for x in self.data])
        return res

    def get_cmd_type_name(self):
        return self.header.get_command_type_string()

    def __str__(self):
        res = "Para_packet:\n"
        res += "-----------\n"
        res += "Header:\n"
        res += "\t{}\n".format(self.header.__str__().replace("\n", "\n\t"))
        if self.data is not None:
            if self.header.version == 0x50:
                res += "Data:\n"
                for index, byte in enumerate(self.data):
                    res += "    Data byte[{0}]: 0X{1:X} ({1})\n".format(index, byte)
            else:  # check if error in data
                if self.header.data_length == 1:
                    res += "\tAn error has been returned: \n"
                    res += "\t============================\n"
                    err_name = self.get_error_name()
                    res += "\t\t(0x{:X})  {}\n".format(self.data[0], err_name)
        else:
            res += "Data = None\n"
        res += "XOR: 0X{:x}\n".format(self.xor)
        return res

    def get_oneliner(self):
        return "H: ( {} ) D: ( {} ) XOR: {}".format(
            ', '.join("0x{:02X}".format(x) for x in self.header.raw),
            ', '.join("0x{:02X}".format(x) for x in self.data),
            '0x{:02X}'.format(self.xor)
        )

    def __len__(self):
        return len(self.raw)


if __name__ == "__main__":
    # normal package
    pp = ParaPacket()
    pp.append_byte(bytes([0x50]))
    pp.append_byte(bytes([0x00]))
    pp.append_byte(bytes([0x02]))
    pp.append_byte(bytes([0x23]))
    pp.append_byte(bytes([0x00]))
    pp.append_byte(bytes([0x00]))
    pp.append_byte(bytes([0x71]))
    # print(pp)
    print(pp.get_oneliner())
    print(pp.crc_check())
    print(pp.is_complete())

    pp = ParaPacket()
    pp.append_byte(bytes([0xF0]))
    pp.append_byte(bytes([0x00]))
    pp.append_byte(bytes([0x01]))
    pp.append_byte(bytes([0x23]))
    pp.append_byte(bytes([0xE0]))
    pp.append_byte(bytes([0x32]))
    # print(pp)
    print(pp.get_oneliner())
    print(pp.crc_check())
    print(pp.is_complete())
