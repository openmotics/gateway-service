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
Base DTO tests
"""

import unittest

from gateway.dto.base import BaseDTO, capture_fields


# Helper classes
class TestFirstDTO(BaseDTO):
    @capture_fields
    def __init__(self, value=None, value_2=None):
        self.value = value
        self.value_2 = value_2


class TestSecondDTO(BaseDTO):
    @capture_fields
    def __init__(self, value=None, value_2=None):
        self.value = value
        self.value_2 = value_2


class BaseDTOTest(unittest.TestCase):

    def assert_dto_equal(self, first, second):
        equal = (first == second)
        self.assertTrue(equal)
        equal = (second == first)
        self.assertTrue(equal)

    def assert_dto_not_equal(self, first, second):
        equal = (first == second)
        self.assertFalse(equal)
        equal = (second == first)
        self.assertFalse(equal)

    def test_dto_equal(self):
        td_1_1 = TestFirstDTO(37)
        td_1_2 = TestFirstDTO(12)
        td_1_3 = TestFirstDTO(37)

        td_2_1 = TestSecondDTO(37)
        td_2_2 = TestSecondDTO(12)
        td_2_3 = TestSecondDTO(37)

        # Test if instance of same class is equal
        self.assert_dto_equal(td_1_1, td_1_3)
        self.assert_dto_not_equal(td_1_1, td_1_2)

        self.assert_dto_equal(td_2_1, td_2_3)
        self.assert_dto_not_equal(td_2_1, td_2_2)

        # Test if instance of different class are not equal
        self.assert_dto_not_equal(td_1_1, td_2_1)
        self.assert_dto_not_equal(td_1_2, td_2_1)

        td_1_4 = TestFirstDTO(None)
        self.assert_dto_not_equal(td_1_1, td_1_4)

        # value not in loaded fields, but should not be equal
        td_1_5 = TestFirstDTO()
        self.assert_dto_not_equal(td_1_5, td_1_1)

        td_1_6 = TestFirstDTO(1)     # This will be (1, None)
        td_1_7 = TestFirstDTO(1, 3)  # This will be (1, 3)
        self.assert_dto_not_equal(td_1_6, td_1_7)
