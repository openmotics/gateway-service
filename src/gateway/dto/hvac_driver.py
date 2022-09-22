from gateway.dto.base import BaseDTO

if False:  # MYPY
    from typing import Any, Optional


class HvacContactDTO(BaseDTO):
    def __init__(self, output_id, mode, value):
        self.output_id = output_id  # type: int
        self.mode = mode  # type: str
        self.value = value  # type: int