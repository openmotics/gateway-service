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

import time
import mock
import xmlrunner

from threading import Thread
from ioc import SetTestMode
from master.core.core_communicator import CoreCommunicator, CommunicationBlocker, CommunicationTimedOutException
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

    def test_communication_blocking(self):
        def _call_in(timeout, callback):
            executed[0] = False

            def _work():
                time.sleep(timeout)
                callback()
                executed[0] = True

            thread = Thread(target=_work)
            thread.start()

        def _wait_for_executed():
            while not executed[0]:
                time.sleep(0.1)

        executed = [False]
        communicator = CoreCommunicator(controller_serial=mock.Mock())
        communicator._send_command = mock.Mock()

        CoreCommunicator.BLOCKER_TIMEOUTS[CommunicationBlocker.RESTART] = 0.5
        communicator.do_command(CoreAPI.device_information_list_inputs(), {}, timeout=None)
        self.assertEqual(1, communicator._send_command.call_count)
        communicator.report_blockage(CommunicationBlocker.RESTART, active=True)
        _call_in(0.25, lambda: communicator.report_blockage(CommunicationBlocker.RESTART, active=False))
        communicator.do_command(CoreAPI.device_information_list_inputs(), {}, timeout=None)
        self.assertEqual(2, communicator._send_command.call_count)
        _wait_for_executed()
        communicator.report_blockage(CommunicationBlocker.RESTART, active=True)
        with self.assertRaises(CommunicationTimedOutException):
            communicator.do_command(CoreAPI.device_information_list_inputs(), {}, timeout=None)
        self.assertEqual(2, communicator._send_command.call_count)
        communicator.report_blockage(CommunicationBlocker.RESTART, active=False)
        communicator.do_command(CoreAPI.device_information_list_inputs(), {}, timeout=None)
        self.assertEqual(3, communicator._send_command.call_count)


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
