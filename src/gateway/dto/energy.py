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
Realtime energy DTO
"""
from gateway.dto.base import BaseDTO
from gateway.enums import EnergyEnums

if False:  # MYPY
    from typing import Optional


class EnergyModuleDTO(BaseDTO):
    def __init__(self, id, name, address, version,  # Main settings
                 # First 8 (mandatory) settings
                 input0, input1, input2, input3, input4, input5, input6, input7,
                 sensor0, sensor1, sensor2, sensor3, sensor4, sensor5, sensor6, sensor7,
                 times0, times1, times2, times3, times4, times5, times6, times7,
                 inverted0, inverted1, inverted2, inverted3, inverted4, inverted5, inverted6, inverted7,
                 # Extra 4 (optional - depending on the version) settings
                 input8=None, input9=None, input10=None, input11=None,
                 sensor8=None, sensor9=None, sensor10=None, sensor11=None,
                 times8=None, times9=None, times10=None, times11=None,
                 inverted8=None, inverted9=None, inverted10=None, inverted11=None):
        # type: (...) -> None
        self.id = id
        self.name = name
        self.address = address
        self.version = version
        self.input0 = input0  # type: str
        self.input1 = input1  # type: str
        self.input2 = input2  # type: str
        self.input3 = input3  # type: str
        self.input4 = input4  # type: str
        self.input5 = input5  # type: str
        self.input6 = input6  # type: str
        self.input7 = input7  # type: str
        self.sensor0 = sensor0  # type: int
        self.sensor1 = sensor1  # type: int
        self.sensor2 = sensor2  # type: int
        self.sensor3 = sensor3  # type: int
        self.sensor4 = sensor4  # type: int
        self.sensor5 = sensor5  # type: int
        self.sensor6 = sensor6  # type: int
        self.sensor7 = sensor7  # type: int
        self.times0 = times0  # type: str
        self.times1 = times1  # type: str
        self.times2 = times2  # type: str
        self.times3 = times3  # type: str
        self.times4 = times4  # type: str
        self.times5 = times5  # type: str
        self.times6 = times6  # type: str
        self.times7 = times7  # type: str
        self.inverted0 = inverted0  # type: bool
        self.inverted1 = inverted1  # type: bool
        self.inverted2 = inverted2  # type: bool
        self.inverted3 = inverted3  # type: bool
        self.inverted4 = inverted4  # type: bool
        self.inverted5 = inverted5  # type: bool
        self.inverted6 = inverted6  # type: bool
        self.inverted7 = inverted7  # type: bool
        self.input8 = input8  # type: Optional[str]
        self.input9 = input9  # type: Optional[str]
        self.input10 = input10  # type: Optional[str]
        self.input11 = input11  # type: Optional[str]
        self.sensor8 = sensor8  # type: Optional[int]
        self.sensor9 = sensor9  # type: Optional[int]
        self.sensor10 = sensor10  # type: Optional[int]
        self.sensor11 = sensor11  # type: Optional[int]
        self.times8 = times8  # type: Optional[str]
        self.times9 = times9  # type: Optional[str]
        self.times10 = times10  # type: Optional[str]
        self.times11 = times11  # type: Optional[str]
        self.inverted8 = inverted8  # type: Optional[bool]
        self.inverted9 = inverted9  # type: Optional[bool]
        self.inverted10 = inverted10  # type: Optional[bool]
        self.inverted11 = inverted11  # type: Optional[bool]
        if EnergyEnums.NUMBER_OF_PORTS[self.version] > 8:
            for i in range(8, 12):
                if (getattr(self, 'input{0}'.format(i)) is None or
                        getattr(self, 'sensor{0}'.format(i)) is None or
                        getattr(self, 'times{0}'.format(i)) is None or
                        getattr(self, 'inverted{0}'.format(i)) is None):
                    raise ValueError('Setings for CTs 9 -> 12 are mandatory')

    @property
    def formatted_address(self):
        if self.version == EnergyEnums.Version.P1_CONCENTRATOR:
            module_type = 'C'
        else:
            module_type = 'E'
        return '{0}{1}'.format(module_type, self.address)


class RealtimeEnergyDTO(BaseDTO):
    def __init__(self, voltage, frequency, current, power):
        # type: (float, float, float, float) -> None
        self.voltage = voltage
        self.frequency = frequency
        self.current = current
        self.power = power


class TotalEnergyDTO(BaseDTO):
    def __init__(self, day, night):
        # type: (int, int) -> None
        self.day = day
        self.night = night
