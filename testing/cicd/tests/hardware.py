import collections

import hypothesis
from hypothesis.strategies import composite, integers, just, lists, one_of

Module = collections.namedtuple('Module', ['name', 'type', 'outputs', 'inputs'])
Output = collections.namedtuple('Output', ['type', 'output_id'])
Input = collections.namedtuple('Input', ['type', 'input_id', 'tester_output_id'])


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
    ]),
    # 'o': Module(name='virtual output', type='o', inputs=[], outputs=[
    #     Output(type='o', output_id=8),
    #     Output(type='o', output_id=9),
    #     Output(type='o', output_id=10),
    #     Output(type='o', output_id=11),
    #     Output(type='o', output_id=12),
    #     Output(type='o', output_id=13),
    #     Output(type='o', output_id=14),
    #     Output(type='o', output_id=15),
    # ]),
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
    ]),
    # 'C': Module(name='CAN control', type='C', outputs=[], inputs=[
    #     # TODO: also test random order discovery?
    #     Input(type='C', input_id=16, tester_output_id=32),
    #     Input(type='C', input_id=17, tester_output_id=33),
    #     Input(type='C', input_id=18, tester_output_id=34),
    #     Input(type='C', input_id=19, tester_output_id=35),
    #     Input(type='C', input_id=20, tester_output_id=36),
    #     Input(type='C', input_id=21, tester_output_id=37),
    # ]),
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
