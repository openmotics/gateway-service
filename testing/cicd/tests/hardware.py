import hypothesis
from hypothesis.strategies import composite, integers, just, lists, one_of
from tests.hardware_layout import OUTPUT_MODULE_LAYOUT, INPUT_MODULE_LAYOUT, ENERGY_MODULE_LAYOUT


def output_types():
    module_types = [module.mtype for module in OUTPUT_MODULE_LAYOUT]
    return one_of([just(x) for x in module_types])


def output_ids(max_value=8):
    assert max_value < 8, 'output modules only contain 8 outputs'
    return integers(min_value=0, max_value=max_value)


@composite
def outputs(draw, types=output_types(), virtual=False):
    module_type = draw(types.filter(lambda x: x != 'o' or virtual))
    assert module_type in ['O', 'o'], 'invalid output type {}'.format(module_type)
    _outputs = []
    for module in OUTPUT_MODULE_LAYOUT:
        _outputs += module.outputs
    output = _outputs[draw(output_ids(len(outputs) - 1))]
    hypothesis.note('Using {} {}#{}'.format(output.module.name, output.module.mtype, output.output_id))
    return output


def multiple_outputs(size, types=output_types()):
    return lists(outputs(types=types), min_size=size, max_size=size, unique_by=lambda x: x.output_id)


def input_types():
    module_types = [module.mtype for module in INPUT_MODULE_LAYOUT]
    return one_of([just(x) for x in module_types])


def input_ids(max_value=8):
    assert max_value < 8, 'input modules only contain 8 inputs'
    return integers(min_value=0, max_value=max_value)


@composite
def inputs(draw, types=input_types()):
    module_type = draw(types)
    assert module_type in ['I', 'i', 'C'], 'invalid input type {}'.format(module_type)
    _inputs = []
    for module in INPUT_MODULE_LAYOUT:
        _inputs += module.inputs
    _input = _inputs[draw(input_ids(len(_inputs) - 1))]
    hypothesis.note('Using {} {}#{}'.format(_input.module.name, _input.module.mtype, _input.input_id))
    return input


def multiple_inputs(size, types=input_types()):
    return lists(inputs(types=types), min_size=size, max_size=size, unique_by=lambda x: x.input_id)


def energy_module_types():
    module_types = [module.mtype for module in ENERGY_MODULE_LAYOUT]
    return one_of([just(x) for x in module_types])


def ct_ids(max_value=12):
    assert max_value < 12, 'energy modules only contain up to 12 inputs'
    return integers(min_value=0, max_value=max_value)


@composite
def cts(draw, types=energy_module_types()):
    module_type = draw(types)
    assert module_type in ['E'], 'invalid energy module type {}'.format(module_type)
    # TODO: For now, there's only one CT actually connected, to always take that one
    ct = ENERGY_MODULE_LAYOUT[0].cts[0]
    hypothesis.note('Using {} {}#{}'.format(ct.module.name, ct.module.mtype, ct.ct_id))
    return ct


def multiple_cts(size, types=energy_module_types()):
    return lists(cts(types=types), min_size=size, max_size=size, unique_by=lambda x: x.ct_id)
