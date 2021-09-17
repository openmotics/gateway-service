# Copyright (C) 2019 OpenMotics BV
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
from __future__ import absolute_import
import unittest

import mock
import xmlrunner

from ioc import SetTestMode
from master.core.core_communicator import CoreCommunicator
from master.core.core_api import CoreAPI


class CoreCommunicatorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def test_do_command_exception_discard_cid(self):
        communicator = CoreCommunicator(controller_serial=mock.Mock())
        with mock.patch.object(communicator, 'discard_cid') as discard:
            self.assertRaises(ValueError, communicator.do_command, CoreAPI.basic_action(), {})
            discard.assert_called_with(3)


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
