# Copyright (C) 2016 OpenMotics BV
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
Tests for MasterCommunicator module.
"""

from __future__ import absolute_import

import threading
import time
import unittest

import xmlrunner
from pytest import mark

from gateway.maintenance_communicator import InMaintenanceModeException
from ioc import SetTestMode, SetUpTestInjections
from master.classic import master_api
from master.classic.master_communicator import BackgroundConsumer, \
    CrcCheckFailedException, MasterCommunicator
from serial_test import DummyPty
from serial_utils import CommunicationTimedOutException


class MasterCommunicatorTest(unittest.TestCase):
    """ Tests for MasterCommunicator class """

    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def test_do_command(self):
        action = master_api.basic_action()
        fields = {'action_type': 1, 'action_number': 2}

        pty = DummyPty([action.create_input(1, fields)])
        SetUpTestInjections(controller_serial=pty)

        comm = MasterCommunicator(init_master=False)
        comm.start()

        pty.master_reply(action.create_output(1, {'resp': 'OK'}))
        output = comm.do_command(action, fields)
        self.assertEqual('OK', output['resp'])

    @mark.slow
    def test_timeout(self):
        action = master_api.basic_action()
        fields = {'action_type': 1, 'action_number': 2}

        pty = DummyPty([action.create_input(1, fields)])
        SetUpTestInjections(controller_serial=pty)

        comm = MasterCommunicator(init_master=False)
        comm.start()

        self.assertRaises(CommunicationTimedOutException, comm.do_command, action, fields)

    def test_timeout_ongoing(self):
        action = master_api.basic_action()
        fields = {'action_type': 1, 'action_number': 2}

        pty = DummyPty([action.create_input(1, fields),
                        action.create_input(2, fields)])
        SetUpTestInjections(controller_serial=pty)

        comm = MasterCommunicator(init_master=False)
        comm.start()

        self.assertRaises(CommunicationTimedOutException, comm.do_command, action, fields,
                          timeout=0.1)

        pty.master_reply(action.create_output(2, {'resp': 'OK'}))
        output = comm.do_command(action, fields)
        self.assertEqual('OK', output['resp'])

    @mark.slow
    def test_split_data(self):
        action = master_api.basic_action()
        fields = {'action_type': 1, 'action_number': 2}

        sequence = []
        for i in range(1, 18):
            sequence.append(action.create_input(i, fields))

        pty = DummyPty(sequence)
        SetUpTestInjections(controller_serial=pty)

        comm = MasterCommunicator(init_master=False)
        comm.start()

        for i in range(1, 18):
            data = action.create_output(i, {'resp': 'OK'})

            ready = threading.Event()

            def write():
                pty.master_reply(data[:i])
                ready.set()
                pty.master_wait()
                pty.fd.write(data[i:])

            thread = threading.Thread(target=write)
            thread.start()

            ready.wait(2)
            output = comm.do_command(action, fields)
            self.assertEqual('OK', output['resp'])
            thread.join(2)
            assert not thread.is_alive()

    def test_passthrough(self):
        pty = DummyPty(['data from passthrough'])
        SetUpTestInjections(controller_serial=pty)

        comm = MasterCommunicator(init_master=False)
        comm.enable_passthrough()
        comm.start()

        pty.master_reply(bytearray(b'got it!'))
        comm.send_passthrough_data(bytearray(b'data from passthrough'))
        self.assertEqual(bytearray(b'got it!'), comm.get_passthrough_data())

    def test_passthrough_with_commands(self):
        action = master_api.basic_action()
        fields = {'action_type': 1, 'action_number': 2}

        pty = DummyPty([action.create_input(1, fields),
                        action.create_input(2, fields),
                        action.create_input(3, fields)])
        SetUpTestInjections(controller_serial=pty)

        comm = MasterCommunicator(init_master=False)
        comm.enable_passthrough()
        comm.start()

        pty.master_reply(bytearray(b'hello') + action.create_output(1, {'resp': 'OK'}))
        self.assertEqual('OK', comm.do_command(action, fields)['resp'])
        self.assertEqual(bytearray(b'hello'), comm.get_passthrough_data())

        pty.master_reply(action.create_output(2, {'resp': 'OK'}) + bytearray(b'world'))
        self.assertEqual('OK', comm.do_command(action, fields)['resp'])
        self.assertEqual(bytearray(b'world'), comm.get_passthrough_data())

        pty.master_reply(bytearray(b'hello') + action.create_output(3, {'resp': 'OK'}) + bytearray(b' world'))
        self.assertEqual('OK', comm.do_command(action, fields)['resp'])
        self.assertEqual(bytearray(b'hello world'), comm.get_passthrough_data())

    def test_maintenance_mode(self):
        action = master_api.basic_action()
        fields = {'action_type': 1, 'action_number': 2}

        pty = DummyPty([master_api.to_cli_mode().create_input(0),
                        bytearray(b'error list\r\n'), bytearray(b'exit\r\n')])
        SetUpTestInjections(controller_serial=pty)

        comm = MasterCommunicator(init_master=False)
        comm.start()

        comm.start_maintenance_mode()
        pty.fd.write(bytearray(b'OK'))
        self.assertRaises(InMaintenanceModeException, comm.do_command, action, fields)
        self.assertEqual(bytearray(b'OK'), comm.get_maintenance_data())

        comm.send_maintenance_data(bytearray(b'error list\r\n'))
        pty.fd.write(bytearray(b'the list\n'))
        self.assertEqual(bytearray(b'the list\n'), comm.get_maintenance_data())

        comm.stop_maintenance_mode()

    def test_maintenance_passthrough(self):
        action = master_api.basic_action()
        fields = {'action_type': 1, 'action_number': 2}

        pty = DummyPty([master_api.to_cli_mode().create_input(0),
                        bytearray(b'error list\r\n'), bytearray(b'exit\r\n')])
        SetUpTestInjections(controller_serial=pty)

        comm = MasterCommunicator(init_master=False)
        comm.enable_passthrough()
        comm.start()

        ready = threading.Event()

        def get_passthrough():
            """ Background thread that reads the passthrough data. """
            self.assertEqual('Before maintenance', comm.get_passthrough_data())
            ready.set()
            self.assertEqual('After maintenance', comm.get_passthrough_data())

        thread = threading.Thread(target=get_passthrough)
        thread.start()

        pty.fd.write(bytearray(b'Before maintenance'))
        ready.wait(2)
        comm.start_maintenance_mode()

        pty.fd.write(bytearray(b'OK'))
        time.sleep(0.2)
        self.assertRaises(InMaintenanceModeException, comm.do_command, action, fields)
        self.assertEqual(bytearray(b'OK'), comm.get_maintenance_data())

        comm.send_maintenance_data(bytearray(b'error list\r\n'))
        pty.fd.write(bytearray(b'the list\n'))
        time.sleep(0.2)
        self.assertEqual(bytearray(b'the list\n'), comm.get_maintenance_data())

        comm.stop_maintenance_mode()
        pty.fd.write(bytearray(b'After maintenance'))

        thread.join(2)
        assert not thread.is_alive()

    def test_background_consumer(self):
        action = master_api.basic_action()
        fields = {'action_type': 1, 'action_number': 2}

        pty = DummyPty([action.create_input(1, fields)])
        SetUpTestInjections(controller_serial=pty)

        got_output = {'phase': 1}

        def callback(output):
            """ Callback that check if the correct result was returned for OL. """
            if got_output['phase'] == 1:
                self.assertEqual([(3, int(12 * 10.0 / 6.0))], output['outputs'])
                got_output['phase'] = 2
            elif got_output['phase'] == 2:
                self.assertEqual([(3, int(12 * 10.0 / 6.0)), (5, int(6 * 10.0 / 6.0))],
                                 output['outputs'])
                got_output['phase'] = 3

        comm = MasterCommunicator(init_master=False)
        comm.enable_passthrough()
        comm.register_consumer(BackgroundConsumer(master_api.output_list(), 0, callback))
        comm.start()

        pty.fd.write(bytearray(b'OL\x00\x01\x03\x0c\r\n'))
        pty.fd.write(bytearray(b'junkOL\x00\x02\x03\x0c\x05\x06\r\n here'))

        pty.master_reply(action.create_output(1, {'resp': 'OK'}))
        output = comm.do_command(action, fields)
        self.assertEqual('OK', output['resp'])

        self.assertEqual(3, got_output['phase'])
        self.assertEqual(bytearray(b'junk here'), comm.get_passthrough_data())

    def test_background_consumer_passthrough(self):
        action = master_api.basic_action()
        fields = {'action_type': 1, 'action_number': 2}

        pty = DummyPty([action.create_input(1, fields)])
        SetUpTestInjections(controller_serial=pty)

        got_output = {'passed': False}

        def callback(output_):
            """ Callback that check if the correct result was returned for OL. """
            self.assertEqual([(3, int(12 * 10.0 / 6.0))], output_['outputs'])
            got_output['passed'] = True

        comm = MasterCommunicator(init_master=False)
        comm.enable_passthrough()
        comm.register_consumer(BackgroundConsumer(master_api.output_list(), 0, callback, True))
        comm.start()

        pty.fd.write(bytearray(b'OL\x00\x01'))
        pty.fd.write(bytearray(b'\x03\x0c\r\n'))

        pty.master_reply(action.create_output(1, {'resp': 'OK'}))
        output = comm.do_command(action, fields)
        self.assertEqual('OK', output['resp'])

        self.assertEqual(True, got_output['passed'])
        self.assertEqual(bytearray(b'OL\x00\x01\x03\x0c\r\n'), comm.get_passthrough_data())

    def test_bytes_counter(self):
        action = master_api.basic_action()
        fields = {'action_type': 1, 'action_number': 2}

        pty = DummyPty([action.create_input(1, fields)])
        SetUpTestInjections(controller_serial=pty)

        comm = MasterCommunicator(init_master=False)
        comm.enable_passthrough()
        comm.start()

        pty.fd.write(bytearray(b'hello'))
        pty.master_reply(action.create_output(1, {'resp': 'OK'}))
        comm.do_command(action, fields)
        self.assertEqual(bytearray(b'hello'), comm.get_passthrough_data())

        self.assertEqual(21, comm.get_communication_statistics()['bytes_written'])
        self.assertEqual(5 + 18, comm.get_communication_statistics()['bytes_read'])

    def test_crc_checking(self):
        action = master_api.sensor_humidity_list()

        fields1 = {}
        for i in range(0, 32):
            fields1['hum%d' % i] = master_api.Svt(master_api.Svt.RAW, i)
        fields1['crc'] = bytearray([ord('C'), 1, 240])

        fields2 = {}
        for i in range(0, 32):
            fields2['hum%d' % i] = master_api.Svt(master_api.Svt.RAW, 2 * i)
        fields2['crc'] = bytearray([ord('C'), 0, 0])

        pty = DummyPty([action.create_input(1),
                        action.create_input(2)])
        SetUpTestInjections(controller_serial=pty)

        comm = MasterCommunicator(init_master=False)
        comm.start()

        pty.master_reply(action.create_output(1, fields1))
        output = comm.do_command(action)
        self.assertEqual(bytearray(b'\x00'), output['hum0'].get_byte())
        self.assertEqual(bytearray(b'\x01'), output['hum1'].get_byte())

        pty.master_reply(action.create_output(2, fields2))
        with self.assertRaises(CrcCheckFailedException):
            comm.do_command(action)


if __name__ == '__main__':
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
