from gateway.dto.base import BaseDTO

if False:  # MYPY
    from typing import Any, Optional


class HvacContactDTO(BaseDTO):
    def __init__(self, output_id=None, output_nr=None, mode=None, value=None):
        self.output_id = output_id  # type: int
        self.output_nr = output_nr  # type: int
        self.mode = mode  # type: str
        self.value = value  # type: int