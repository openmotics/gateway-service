import hypothesis
from hypothesis.strategies import composite, integers, just, lists, one_of
from tests.hardware_layout import OUTPUT_MODULE_LAYOUT, INPUT_MODULE_LAYOUT, ENERGY_MODULE_LAYOUT, Module, TEST_PLATFORM


def output_types(virtual=False):
    module_types = [module.mtype for module in OUTPUT_MODULE_LAYOUT
                    if virtual is True or module.hardware_type != Module.HardwareType.VIRTUAL]
    return one_of([just(x) for x in module_types])


@composite
def outputs(draw, types=None, virtual=False):
    if types is None:
        types = output_types(virtual=virtual)
    module_type = draw(types)
    assert module_type in ['O', 'o'], 'Invalid output type {}'.format(module_type)
    _outputs = []
    for module in OUTPUT_MODULE_LAYOUT:
        if module.mtype != module_type:
            continue
        if not virtual and module.hardware_type == Module.HardwareType.VIRTUAL:
            continue
        _outputs += module.outputs
    output = _outputs[draw(integers(min_value=0, max_value=len(_outputs) - 1))]
    hypothesis.note('Using {} {}'.format(output.module.name, output))
    return output


def multiple_outputs(size, types=output_types()):
    return lists(outputs(types=types), min_size=size, max_size=size, unique_by=lambda x: x.output_id)


def input_types():
    module_types = [module.mtype for module in INPUT_MODULE_LAYOUT]
    return one_of([just(x) for x in module_types])


@composite
def inputs(draw, types=input_types()):
    module_type = draw(types)
    assert module_type in ['I', 'i', 'C'], 'Invalid input type {}'.format(module_type)
    _inputs = []
    for module in INPUT_MODULE_LAYOUT:
        if module.mtype != module_type:
            continue
        _inputs += module.inputs
    _input = _inputs[draw(integers(min_value=0, max_value=len(_inputs) - 1))]
    hypothesis.note('Using {} {}'.format(_input.module.name, _input))
    return _input


def multiple_inputs(size, types=input_types()):
    return lists(inputs(types=types), min_size=size, max_size=size, unique_by=lambda x: x.input_id)


def energy_module_types():
    module_types = [module.mtype for module in ENERGY_MODULE_LAYOUT]
    return one_of([just(x) for x in module_types])


def ct_ids(max_value=12):
    assert max_value < 12, 'Energy modules only contain up to 12 inputs'
    return integers(min_value=0, max_value=max_value)


@composite
def cts(draw, types=energy_module_types()):
    module_type = draw(types)
    assert module_type in ['E'], 'Invalid energy module type {}'.format(module_type)
    # TODO: For now, there's only one CT actually connected, to always take that one
    ct = ENERGY_MODULE_LAYOUT[0].cts[0]
    hypothesis.note('Using {} {}'.format(ct.module.name, ct))
    return ct


def multiple_cts(size, types=energy_module_types()):
    return lists(cts(types=types), min_size=size, max_size=size, unique_by=lambda x: x.ct_id)


def skip_on_platforms(platforms):
    return TEST_PLATFORM in platforms
