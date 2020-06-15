import collections

import hypothesis
from hypothesis.strategies import composite, integers, just, lists, one_of

Module = collections.namedtuple('Module', ['name', 'type', 'outputs', 'inputs', 'cts'])
Output = collections.namedtuple('Output', ['type', 'output_id'])
Input = collections.namedtuple('Input', ['type', 'input_id', 'tester_output_id'])
CT = collections.namedtuple('CT', ['module_id', 'ct_id'])


OUTPUT_MODULE_LAYOUT = {
    'O': Module(name='output module', type='O', inputs=[], outputs=[
        Output(type='O', output_id=0),
        Output(type='O', output_id=1),
        Output(type='O', output_id=2),
        Output(type='O', output_id=3),
        Output(type='O', output_id=4),
        Output(type='O', output_id=5),
        Output(type='O', output_id=6),
        Output(type='O', output_id=7),
    ], cts=[]),
    # 'o': Module(name='virtual output', type='o', inputs=[], outputs=[
    #     Output(type='o', output_id=8),
    #     Output(type='o', output_id=9),
    #     Output(type='o', output_id=10),
    #     Output(type='o', output_id=11),
    #     Output(type='o', output_id=12),
    #     Output(type='o', output_id=13),
    #     Output(type='o', output_id=14),
    #     Output(type='o', output_id=15),
    # ], cts=[]),
}

INPUT_MODULE_LAYOUT = {
    'I': Module(name='input module', type='I', outputs=[], inputs=[
        Input(type='I', input_id=0, tester_output_id=0),
        Input(type='I', input_id=1, tester_output_id=1),
        Input(type='I', input_id=2, tester_output_id=2),
        Input(type='I', input_id=3, tester_output_id=3),
        Input(type='I', input_id=4, tester_output_id=4),
        Input(type='I', input_id=5, tester_output_id=5),
        Input(type='I', input_id=6, tester_output_id=6),
        Input(type='I', input_id=7, tester_output_id=7),
    ], cts=[]),
    # 'C': Module(name='CAN control', type='C', outputs=[], inputs=[
    #     # TODO: also test random order discovery?
    #     Input(type='C', input_id=16, tester_output_id=32),
    #     Input(type='C', input_id=17, tester_output_id=33),
    #     Input(type='C', input_id=18, tester_output_id=34),
    #     Input(type='C', input_id=19, tester_output_id=35),
    #     Input(type='C', input_id=20, tester_output_id=36),
    #     Input(type='C', input_id=21, tester_output_id=37),
    # ], cts=[]),
}

ENERGY_MODULE_LAYOUT = {
    'E': Module(name='energy_module', type='E', outputs=[], inputs=[],
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
}


def output_types():
    module_types = OUTPUT_MODULE_LAYOUT.keys()
    return one_of([just(x) for x in module_types])


def output_ids(max_value=8):
    assert max_value < 8, 'output modules only contain 8 outputs'
    return integers(min_value=0, max_value=max_value)


@composite
def outputs(draw, types=output_types()):
    module_type = draw(types)
    assert module_type in ['O', 'o'], 'invalid output type {}'.format(module_type)
    module = OUTPUT_MODULE_LAYOUT[module_type]
    output = module.outputs[draw(output_ids(len(module.outputs) - 1))]
    hypothesis.note('Using {} {}#{}'.format(module.name, module.type, output.output_id))
    return output


def multiple_outputs(size, types=output_types()):
    return lists(outputs(types=types), min_size=size, max_size=size, unique_by=lambda x: x.output_id)


def input_types():
    module_types = INPUT_MODULE_LAYOUT.keys()
    return one_of([just(x) for x in module_types])


def input_ids(max_value=8):
    assert max_value < 8, 'input modules only contain 8 inputs'
    return integers(min_value=0, max_value=max_value)


@composite
def inputs(draw, types=input_types()):
    module_type = draw(types)
    assert module_type in ['I', 'i', 'C'], 'invalid input type {}'.format(module_type)
    module = INPUT_MODULE_LAYOUT[module_type]
    input = module.inputs[draw(input_ids(len(module.inputs) - 1))]
    hypothesis.note('Using {} {}#{}'.format(module.name, module.type, input.input_id))
    return input


def multiple_inputs(size, types=input_types()):
    return lists(inputs(types=types), min_size=size, max_size=size, unique_by=lambda x: x.input_id)


def energy_module_types():
    module_types = ENERGY_MODULE_LAYOUT.keys()
    return one_of([just(x) for x in module_types])


def ct_ids(max_value=12):
    assert max_value < 12, 'energy modules only contain up to 12 inputs'
    return integers(min_value=0, max_value=max_value)


@composite
def cts(draw, types=energy_module_types()):
    module_type = draw(types)
    assert module_type in ['E'], 'invalid energy module type {}'.format(module_type)
    module = ENERGY_MODULE_LAYOUT[module_type]
    # ct = module.cts[draw(ct_ids(len(module.cts) - 1))]
    ct = module.cts[0]  # TODO: Use all CTs once they are all connected
    hypothesis.note('Using {} {}#{}'.format(module.name, module.type, ct.ct_id))
    return input


def multiple_cts(size, types=energy_module_types()):
    return lists(cts(types=types), min_size=size, max_size=size, unique_by=lambda x: x.ct_id)
