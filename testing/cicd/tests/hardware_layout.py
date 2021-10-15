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
        temp = 5  # PWR_DUT_CL_TEMP

    class Buttons(object):
        dut = [8]  # BTN_DUT_CL

    class Button(object):  # TODO: Move to module layout by adding the buttons as a property to the module
        energy = 9  # BTN_DUT_CL_EY
        input = 10  # BTN_DUT_CL_IN
        output = 11  # BTN_DUT_CL_OT
        shutter = 12  # BTN_DUT_CL_SR
        dimmer = 13  # BTN_DUT_CL_DL
        temp = 14  # BTN_DUT_CL_TMP
        can = 15  # BTN_DUT_CL_CC


class CorePlusTesterOutputs(object):
    class Power(object):
        dut = 6  # PWR_DUT_BS
        bus1 = 7  # PWR_DUT_BS_BUS1

    class Buttons(object):
        dut = [32, 35]  # BTN_DUT_BS_ACT (action) and BTN_DUT_BS_STP (setup)

    class Button(object):  # TODO: Move to module layout by adding the buttons as a property to the module
        action = 32  # BTN_DUT_BS_ACT
        select = 33  # BTN_DUT_BS_SEL
        can_power = 34  # BTN_DUT_BS_CPWR
        setup = 35  # BTN_DUT_BS_STP
        input = 36  # BTN_DUT_BS_IT
        output = 37  # BTN_DUT_BS_RY


if TEST_PLATFORM == TestPlatform.DEBIAN:
    TESTER = ClassicTesterOutputs
else:
    TESTER = CorePlusTesterOutputs


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


class Shutter(object):
    def __init__(self, shutter_id, tester_input_id_up, tester_input_id_down, module=None):
        self.shutter_id = shutter_id
        self.tester_input_id_up = tester_input_id_up
        self.tester_input_id_down = tester_input_id_down
        self.module = module

    def __str__(self):
        return 'Shutter({0}#{1})'.format(
            '?' if self.module is None else self.module.mtype,
            self.shutter_id
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

    def __init__(self, name, mtype, hardware_type, is_can=False, inputs=None, cts=None, outputs=None, temps=None, shutters=None):
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
        self.shutters = []
        for shutter in (shutters or []):
            shutter.module = self
            self.shutters.append(shutter)


_OUTPUT_MODULE_LAYOUTS = {
    TestPlatform.CORE_PLUS: [
        Module(name='internal output module 0-7', mtype='o',
               hardware_type=Module.HardwareType.INTERNAL,
               outputs=[Output(output_id=0, tester_input_id=16),
                        Output(output_id=1, tester_input_id=17),
                        Output(output_id=2, tester_input_id=18),
                        Output(output_id=3, tester_input_id=19),
                        Output(output_id=4, tester_input_id=20),
                        Output(output_id=5, tester_input_id=21),
                        Output(output_id=6, tester_input_id=22),
                        Output(output_id=7, tester_input_id=23)]),
        Module(name='internal output module 8-15', mtype='o',
               hardware_type=Module.HardwareType.INTERNAL,
               outputs=[Output(output_id=8, tester_input_id=24),
                        Output(output_id=9, tester_input_id=25),
                        Output(output_id=10, tester_input_id=26),
                        Output(output_id=11, tester_input_id=27),
                        Output(output_id=12, tester_input_id=28),
                        Output(output_id=13, tester_input_id=29),
                        Output(output_id=14, tester_input_id=30),
                        Output(output_id=15, tester_input_id=31)]),
        Module(name='internal open collector module', mtype='l',
               hardware_type=Module.HardwareType.INTERNAL,
               outputs=[Output(output_id=23, tester_input_id=39)]),
        Module(name='output module', mtype='O',
               hardware_type=Module.HardwareType.PHYSICAL,
               outputs=[Output(output_id=32, tester_input_id=40),
                        Output(output_id=33, tester_input_id=41),
                        Output(output_id=34, tester_input_id=42),
                        Output(output_id=35, tester_input_id=43),
                        Output(output_id=36, tester_input_id=44),
                        Output(output_id=37, tester_input_id=45),
                        Output(output_id=38, tester_input_id=46),
                        Output(output_id=39, tester_input_id=47)])
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
                        Output(output_id=7, tester_input_id=15)]),
        Module(name='dimmer module', mtype='D',
               hardware_type=Module.HardwareType.PHYSICAL,
               outputs=[]),
        Module(name='virtual output', mtype='o',
               hardware_type=Module.HardwareType.VIRTUAL,
               outputs=[Output(output_id=16, tester_input_id=None),
                        Output(output_id=17, tester_input_id=None),
                        Output(output_id=18, tester_input_id=None),
                        Output(output_id=19, tester_input_id=None),
                        Output(output_id=20, tester_input_id=None),
                        Output(output_id=21, tester_input_id=None),
                        Output(output_id=22, tester_input_id=None),
                        Output(output_id=23, tester_input_id=None)])
    ]
}
OUTPUT_MODULE_LAYOUT = _OUTPUT_MODULE_LAYOUTS[TEST_PLATFORM]  # type: List[Module]

_SHUTTER_MODULE_LAYOUT = {
    TestPlatform.CORE_PLUS: [
        # TODO: Change code to support flexible output/shutter changes
        Module(name='internal output module 0-7 as shutter', mtype='r',
               hardware_type=Module.HardwareType.INTERNAL,
               shutters=[Shutter(shutter_id=0, tester_input_id_up=16, tester_input_id_down=17),
                         Shutter(shutter_id=1, tester_input_id_up=18, tester_input_id_down=19),
                         Shutter(shutter_id=2, tester_input_id_up=20, tester_input_id_down=21),
                         Shutter(shutter_id=3, tester_input_id_up=22, tester_input_id_down=23)]),
        Module(name='internal output module 8-15 as shutter', mtype='r',
               hardware_type=Module.HardwareType.INTERNAL,
               shutters=[Shutter(shutter_id=4, tester_input_id_up=24, tester_input_id_down=25),
                         Shutter(shutter_id=5, tester_input_id_up=26, tester_input_id_down=27),
                         Shutter(shutter_id=6, tester_input_id_up=28, tester_input_id_down=29),
                         Shutter(shutter_id=7, tester_input_id_up=30, tester_input_id_down=31)]),
    ],
    TestPlatform.DEBIAN: [
        Module(name='shutter module', mtype='R',
               hardware_type=Module.HardwareType.PHYSICAL,
               shutters=[Shutter(shutter_id=0, tester_input_id_up=0, tester_input_id_down=1),
                         Shutter(shutter_id=1, tester_input_id_up=2, tester_input_id_down=3),
                         Shutter(shutter_id=2, tester_input_id_up=4, tester_input_id_down=5),
                         Shutter(shutter_id=3, tester_input_id_up=6, tester_input_id_down=7)])
    ]
}
SHUTTER_MODULE_LAYOUT = _SHUTTER_MODULE_LAYOUT[TEST_PLATFORM]  # type: List[Module]

_INPUT_MODULE_LAYOUTS = {
    TestPlatform.CORE_PLUS: [
        Module(name='internal input module', mtype='i',
               hardware_type=Module.HardwareType.INTERNAL,
               inputs=[Input(input_id=0, tester_output_id=40),
                       Input(input_id=1, tester_output_id=41),
                       Input(input_id=2, tester_output_id=42),
                       Input(input_id=3, tester_output_id=43),
                       Input(input_id=4, tester_output_id=44)]),
        Module(name='input module', mtype='I',
               hardware_type=Module.HardwareType.PHYSICAL,
               inputs=[Input(input_id=8, tester_output_id=48),
                       Input(input_id=9, tester_output_id=49),
                       Input(input_id=10, tester_output_id=50),
                       Input(input_id=11, tester_output_id=51),
                       Input(input_id=12, tester_output_id=52),
                       Input(input_id=13, tester_output_id=53),
                       Input(input_id=14, tester_output_id=54),
                       Input(input_id=15, tester_output_id=55)]),
        Module(name='CC emulated input module', mtype='I', is_can=True,
               hardware_type=Module.HardwareType.EMULATED,
               inputs=[Input(input_id=16, tester_output_id=45),
                       Input(input_id=17, tester_output_id=46),
                       Input(input_id=18, tester_output_id=47)])
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
        Module(name='CC module', mtype='C',
               hardware_type=Module.HardwareType.PHYSICAL,
               inputs=[]),
        Module(name='CC emulated input module 0', mtype='I', is_can=True,
               hardware_type=Module.HardwareType.EMULATED,
               inputs=[Input(input_id=24, tester_output_id=16),
                       Input(input_id=25, tester_output_id=17),
                       Input(input_id=26, tester_output_id=18),
                       Input(input_id=27, tester_output_id=19),
                       Input(input_id=28, tester_output_id=20),
                       Input(input_id=29, tester_output_id=21)])
        #                Input(input_id=30, tester_output_id=56),  # Start the long uCAN bus
        #                Input(input_id=31, tester_output_id=57)]),
        # Module(name='CC emulated input module 1', mtype='I', is_can=True,
        #        hardware_type=Module.HardwareType.EMULATED,
        #        inputs=[Input(input_id=40, tester_output_id=58),
        #                Input(input_id=41, tester_output_id=59),
        #                Input(input_id=42, tester_output_id=60),
        #                Input(input_id=43, tester_output_id=61),
        #                Input(input_id=44, tester_output_id=62),
        #                Input(input_id=45, tester_output_id=63),
        #                Input(input_id=46, tester_output_id=64),
        #                Input(input_id=47, tester_output_id=65)]),
        # Module(name='CC emulated input module 2', mtype='I', is_can=True,
        #        hardware_type=Module.HardwareType.EMULATED,
        #        inputs=[Input(input_id=48, tester_output_id=66)])
    ]
}
INPUT_MODULE_LAYOUT = _INPUT_MODULE_LAYOUTS[TEST_PLATFORM]  # type: List[Module]

_TEMPERATURE_MODULE_LAYOUTS = {
    TestPlatform.CORE_PLUS: [],
    TestPlatform.DEBIAN: [
        Module(name='temperature module', mtype='T',
               hardware_type=Module.HardwareType.PHYSICAL,
               temps=[]),
        Module(name='CC emulated temperature module 0', mtype='T', is_can=True,
               hardware_type=Module.HardwareType.EMULATED,
               temps=[]),
        # Module(name='CC emulated temperature module 1', mtype='T', is_can=True,
        #        hardware_type=Module.HardwareType.EMULATED,
        #        temps=[])
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
               cts=[CT(module_id=2, ct_id=0),
                    CT(module_id=2, ct_id=1),
                    CT(module_id=2, ct_id=2),
                    CT(module_id=2, ct_id=3),
                    CT(module_id=2, ct_id=4),
                    CT(module_id=2, ct_id=5),
                    CT(module_id=2, ct_id=6),
                    CT(module_id=2, ct_id=7),
                    CT(module_id=2, ct_id=8),
                    CT(module_id=2, ct_id=9),
                    CT(module_id=2, ct_id=10),
                    CT(module_id=2, ct_id=11)])
    ]
}
ENERGY_MODULE_LAYOUT = _ENERGY_MODULE_LAYOUTS[TEST_PLATFORM]  # type: List[Module]
# TODO: There is no energy module in the Core+ setup at this moment, so to prevent failures from tests
#       the Debian modules will be selected, and the test itself will skip based on the platform
