import os

if False:  # MYPY
    from typing import List


class TestPlatform(object):
    CORE_PLUS = 'CORE_PLUS'
    DEBIAN = 'DEBIAN'


TEST_PLATFORM = os.environ['TEST_PLATFORM']


class ClassicTesterOutputs(object):
    class Power(object):
        dut = 0  # PWR_DUT_CL
        bus2 = 1  # PWR_DUT_CL_BUS2
        bus1 = 2  # PWR_DUT_CL_BUS1
        cc = 3  # PWR_DUT_CL_CAN
        dali = 4  # PWR_DUT_CL_DALI
        temp = 5  # PWR_DUT_CL_TMEP

    class Buttons(object):
        dut = [8]  # BTN_DUT_CL

    class Button(object):
        energy = 9  # BTN_DUT_CL_EY
        input = 10  # BTN_DUT_CL_IN
        output = 11  # BTN_DUT_CL_OUT
        shutter = 12  # BTN_DUT_CL_SHT
        dimmer = 13  # BTN_DUT_CL_DIM
        temp = 14  # BTN_DUT_CL_TMP
        can = 15  # BTN_DUT_CL_CC


# TODO: handle Core+ here
TESTER = ClassicTesterOutputs


class Output(object):
    def __init__(self, output_id, tester_input_id, module=None):
        self.output_id = output_id
        self.tester_input_id = tester_input_id
        self.module = module

    def __str__(self):
        return 'Output({0}#{1})'.format(
            '?' if self.module is None else self.module.mtype,
            self.output_id
        )

    def __repr__(self):
        return str(self)


class Input(object):
    def __init__(self, input_id, tester_output_id, module=None, is_dimmer=False):
        self.input_id = input_id
        self.tester_output_id = tester_output_id
        self.is_dimmer = is_dimmer
        self.module = module

    def __str__(self):
        return 'Input({0}#{1}{2})'.format(
            '?' if self.module is None else self.module.mtype,
            self.input_id,
            ', ucan' if self.module.is_can else ''
        )

    def __repr__(self):
        return str(self)


class CT(object):
    def __init__(self, module_id, ct_id, module=None):
        self.module_id = module_id
        self.ct_id = ct_id
        self.module = module

    def __str__(self):
        return 'CT({0}#{1}.{2})'.format(
            '?' if self.module is None else self.module.mtype,
            self.module_id, self.ct_id
        )

    def __repr__(self):
        return str(self)


class Module(object):
    class HardwareType(object):
        VIRTUAL = 'virtual'
        PHYSICAL = 'physical'
        EMULATED = 'emulated'
        INTERNAL = 'internal'

    def __init__(self, name, mtype, hardware_type, is_can=False, inputs=None, cts=None, outputs=None, temps=None):
        self.name = name
        self.mtype = mtype
        self.hardware_type = hardware_type
        self.is_can = is_can
        self.inputs = []
        for _input in (inputs or []):
            _input.module = self
            self.inputs.append(_input)
        self.cts = []
        for ct in (cts or []):
            ct.module = self
            self.cts.append(ct)
        self.outputs = []
        for output in (outputs or []):
            output.module = self
            self.outputs.append(output)
        self.temps = []
        for temp in (temps or []):
            temp.module = self
            self.temps.append(temp)


_OUTPUT_MODULE_LAYOUTS = {
    TestPlatform.CORE_PLUS: [
        # TODO: Add support for open-collector outputs, that are connected
        #       with a dim control on the tester
    ],
    TestPlatform.DEBIAN: [
        Module(name='output module', mtype='O',
               hardware_type=Module.HardwareType.PHYSICAL,
               outputs=[Output(output_id=0, tester_input_id=8),
                        Output(output_id=1, tester_input_id=9),
                        Output(output_id=2, tester_input_id=10),
                        Output(output_id=3, tester_input_id=11),
                        Output(output_id=4, tester_input_id=12),
                        Output(output_id=5, tester_input_id=13),
                        Output(output_id=6, tester_input_id=14),
                        Output(output_id=7, tester_input_id=15)
                        ]),
        Module(name='shutter module', mtype='R',
               hardware_type=Module.HardwareType.PHYSICAL,
               outputs=[]),
        Module(name='dimmer module', mtype='D',
               hardware_type=Module.HardwareType.PHYSICAL,
               outputs=[]),
        Module(name='virtual output', mtype='o',
               hardware_type=Module.HardwareType.VIRTUAL,
               outputs=[Output(output_id=24, tester_input_id=None),
                        Output(output_id=25, tester_input_id=None),
                        Output(output_id=26, tester_input_id=None),
                        Output(output_id=27, tester_input_id=None),
                        Output(output_id=28, tester_input_id=None),
                        Output(output_id=29, tester_input_id=None),
                        Output(output_id=30, tester_input_id=None),
                        Output(output_id=31, tester_input_id=None)])
    ]
}
OUTPUT_MODULE_LAYOUT = _OUTPUT_MODULE_LAYOUTS[TEST_PLATFORM]  # type: List[Module]

_INPUT_MODULE_LAYOUTS = {
    TestPlatform.CORE_PLUS: [
        # TODO
    ],
    TestPlatform.DEBIAN: [
        Module(name='input module', mtype='I',
               hardware_type=Module.HardwareType.PHYSICAL,
               inputs=[Input(input_id=0, tester_output_id=24),
                       Input(input_id=1, tester_output_id=25),
                       Input(input_id=2, tester_output_id=26),
                       Input(input_id=3, tester_output_id=27),
                       Input(input_id=4, tester_output_id=28),
                       Input(input_id=5, tester_output_id=29),
                       Input(input_id=6, tester_output_id=30),
                       Input(input_id=7, tester_output_id=31)]),
        Module(name='CAN control', mtype='I', is_can=True,
               hardware_type=Module.HardwareType.EMULATED,
               inputs=[Input(input_id=24, tester_output_id=16),
                       Input(input_id=25, tester_output_id=17),
                       Input(input_id=26, tester_output_id=18),
                       Input(input_id=27, tester_output_id=19),
                       Input(input_id=28, tester_output_id=20),
                       Input(input_id=29, tester_output_id=21)]),
    ]
}
INPUT_MODULE_LAYOUT = _INPUT_MODULE_LAYOUTS[TEST_PLATFORM]  # type: List[Module]

_TEMPERATURE_MODULE_LAYOUTS = {
    TestPlatform.CORE_PLUS: [],
    TestPlatform.DEBIAN: [
        Module(name='temperature module', mtype='T',
               hardware_type=Module.HardwareType.PHYSICAL,
               temps=[]),
        Module(name='CAN control', mtype='T', is_can=True,
               hardware_type=Module.HardwareType.EMULATED,
               temps=[]),
    ],
}
TEMPERATURE_MODULE_LAYOUT = _TEMPERATURE_MODULE_LAYOUTS[TEST_PLATFORM]  # type: List[Module]

_ENERGY_MODULE_LAYOUTS = {
    TestPlatform.CORE_PLUS: [
        # TODO: Add energy module to the Core+
    ],
    TestPlatform.DEBIAN: [
        Module(name='energy_module', mtype='E',
               hardware_type=Module.HardwareType.PHYSICAL,
               cts=[CT(module_id=1, ct_id=0),
                    CT(module_id=1, ct_id=1),
                    CT(module_id=1, ct_id=2),
                    CT(module_id=1, ct_id=3),
                    CT(module_id=1, ct_id=4),
                    CT(module_id=1, ct_id=5),
                    CT(module_id=1, ct_id=6),
                    CT(module_id=1, ct_id=7),
                    CT(module_id=1, ct_id=8),
                    CT(module_id=1, ct_id=9),
                    CT(module_id=1, ct_id=10),
                    CT(module_id=1, ct_id=11)])
    ]
}
ENERGY_MODULE_LAYOUT = _ENERGY_MODULE_LAYOUTS[TEST_PLATFORM]  # type: List[Module]
# TODO: There is no energy module in the Core+ setup at this moment, so to prevent failures from tests
#       the Debian modules will be selected, and the test itself will skip based on the platform
