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
    def __init__(self, value):
        self.value = value


class TestSecondDTO(BaseDTO):
    @capture_fields
    def __init__(self, value):
        self.value = value


class BaseDTOTest(unittest.TestCase):

    def test_dto_equal(self):
        td_1_1 = TestFirstDTO(37)
        td_1_2 = TestFirstDTO(12)
        td_1_3 = TestFirstDTO(37)

        td_2_1 = TestSecondDTO(37)
        td_2_2 = TestSecondDTO(12)
        td_2_3 = TestSecondDTO(37)

        # Test if instance of same class is equal
        self.assertEqual(td_1_1, td_1_3)
        self.assertNotEqual(td_1_1, td_1_2)

        self.assertEqual(td_2_1, td_2_3)
        self.assertNotEqual(td_2_1, td_2_2)

        # Test if instance of different class are not equal
        self.assertNotEqual(td_1_1, td_2_1)
        self.assertNotEqual(td_1_2, td_2_1)

        td_1_4 = TestFirstDTO(None)
        self.assertNotEqual(td_1_1, td_1_4)

