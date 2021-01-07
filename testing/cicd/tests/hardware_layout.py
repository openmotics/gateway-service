import os

if False:  # MYPY
    from typing import List


class TestPlatform(object):
    CORE_PLUS = 'CORE_PLUS'
    DEBIAN = 'DEBIAN'


TEST_PLATFORM = os.environ['TEST_PLATFORM']


class Output(object):
    def __init__(self, output_id, module=None):
        self.output_id = output_id
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
        return 'Input({0}#{1})'.format(
            '?' if self.module is None else self.module.mtype,
            self.input_id
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

    def __init__(self, name, mtype, hardware_type, inputs=None, cts=None, outputs=None):
        self.name = name
        self.mtype = mtype
        self.hardware_type = hardware_type
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


_OUTPUT_MODULE_LAYOUTS = {
    TestPlatform.CORE_PLUS: [
        # TODO: Add support for open-collector outputs, that are connected
        #       with a dim control on the tester
        Module(name='output module 0', mtype='o',
               hardware_type=Module.HardwareType.INTERNAL,
               outputs=[Output(output_id=0),
                        Output(output_id=1),
                        Output(output_id=2),
                        Output(output_id=3),
                        Output(output_id=4),
                        Output(output_id=5),
                        Output(output_id=6),
                        Output(output_id=7)]),
        Module(name='output module 1', mtype='o',
               hardware_type=Module.HardwareType.INTERNAL,
               outputs=[Output(output_id=8),
                        Output(output_id=9),
                        Output(output_id=10),
                        Output(output_id=11),
                        Output(output_id=12),
                        Output(output_id=13),
                        Output(output_id=14),
                        Output(output_id=15)])
    ],
    TestPlatform.DEBIAN: [
        Module(name='output module', mtype='O',
               hardware_type=Module.HardwareType.PHYSICAL,
               outputs=[Output(output_id=0),
                        Output(output_id=1),
                        Output(output_id=2),
                        Output(output_id=3),
                        Output(output_id=4),
                        Output(output_id=5),
                        Output(output_id=6),
                        Output(output_id=7)]),
        Module(name='virtual output', mtype='o',
               hardware_type=Module.HardwareType.VIRTUAL,
               outputs=[Output(output_id=8),
                        Output(output_id=9),
                        Output(output_id=10),
                        Output(output_id=11),
                        Output(output_id=12),
                        Output(output_id=13),
                        Output(output_id=14),
                        Output(output_id=15)])
    ]
}
OUTPUT_MODULE_LAYOUT = _OUTPUT_MODULE_LAYOUTS[TEST_PLATFORM]  # type: List[Module]

_INPUT_MODULE_LAYOUTS = {
    TestPlatform.CORE_PLUS: [
        Module(name='input module', mtype='i',
               hardware_type=Module.HardwareType.INTERNAL,
               inputs=[Input(input_id=0, tester_output_id=24, is_dimmer=True),
                       Input(input_id=1, tester_output_id=25, is_dimmer=True),
                       Input(input_id=2, tester_output_id=26, is_dimmer=True),
                       Input(input_id=3, tester_output_id=27, is_dimmer=True)])  # Only 4 inputs are wired up
    ],
    TestPlatform.DEBIAN: [
        Module(name='input module', mtype='I',
               hardware_type=Module.HardwareType.PHYSICAL,
               inputs=[Input(input_id=0, tester_output_id=0),
                       Input(input_id=1, tester_output_id=1),
                       Input(input_id=2, tester_output_id=2),
                       Input(input_id=3, tester_output_id=3),
                       Input(input_id=4, tester_output_id=4),
                       Input(input_id=5, tester_output_id=5),
                       Input(input_id=6, tester_output_id=6),
                       Input(input_id=7, tester_output_id=7)]),
        # TODO: also test random order discovery?
        Module(name='CAN control', mtype='i',
               hardware_type=Module.HardwareType.EMULATED,
               inputs=[Input(input_id=16, tester_output_id=32),
                       Input(input_id=17, tester_output_id=33),
                       Input(input_id=18, tester_output_id=34),
                       Input(input_id=19, tester_output_id=35),
                       Input(input_id=20, tester_output_id=36),
                       Input(input_id=21, tester_output_id=37)])
    ]
}
INPUT_MODULE_LAYOUT = _INPUT_MODULE_LAYOUTS[TEST_PLATFORM]  # type: List[Module]

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
