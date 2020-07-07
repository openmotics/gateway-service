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
Tests for the pulses module.

@author: fryckbos
"""

from __future__ import absolute_import
import unittest
import xmlrunner
from peewee import SqliteDatabase, DoesNotExist
from mock import Mock

from ioc import SetTestMode, SetUpTestInjections
from gateway.dto import PulseCounterDTO
from gateway.pulse_counter_controller import PulseCounterController
from gateway.hal.master_controller_classic import MasterClassicController
from gateway.models import PulseCounter, Room

MODELS = [PulseCounter, Room]


class PulseCounterControllerTest(unittest.TestCase):
    """ Tests for PulseCounterController. """

    FILE = 'test.db'

    @classmethod
    def setUpClass(cls):
        SetTestMode()
        cls.test_db = SqliteDatabase(':memory:')

    def setUp(self):  # pylint: disable=C0103
        """ Run before each test. """
        self.maxDiff = None
        self.test_db.bind(MODELS, bind_refs=False, bind_backrefs=False)
        self.test_db.connect()
        self.test_db.create_tables(MODELS)

    def tearDown(self):  # pylint: disable=C0103
        """ Run after each test. """
        self.test_db.drop_tables(MODELS)
        self.test_db.close()

    def test_pulse_counter_up_down(self):
        """ Test adding and removing pulse counters. """
        SetUpTestInjections(master_controller=Mock(),
                            maintenance_controller=Mock())
        controller = PulseCounterController()

        for i in range(24):
            PulseCounter(number=i, name='PulseCounter {0}'.format(i), source='master', persistent=False).save()

        # Only master pulse counters
        controller.set_amount_of_pulse_counters(24)
        self.assertEqual(24, controller.get_amount_of_pulse_counters())

        # Add virtual pulse counters
        controller.set_amount_of_pulse_counters(28)
        self.assertEqual(28, controller.get_amount_of_pulse_counters())

        # Add virtual pulse counter
        controller.set_amount_of_pulse_counters(29)
        self.assertEqual(29, controller.get_amount_of_pulse_counters())

        # Remove virtual pulse counter
        controller.set_amount_of_pulse_counters(28)
        self.assertEqual(28, controller.get_amount_of_pulse_counters())

        # Set virtual pulse counters to 0
        controller.set_amount_of_pulse_counters(24)
        self.assertEqual(24, controller.get_amount_of_pulse_counters())

        # Set the number of pulse counters to low
        with self.assertRaises(ValueError):
            controller.set_amount_of_pulse_counters(23)

    def test_pulse_counter_status(self):
        data = {'pv0': 0, 'pv1': 1, 'pv2': 2, 'pv3': 3, 'pv4': 4, 'pv5': 5, 'pv6': 6, 'pv7': 7,
                'pv8': 8, 'pv9': 9, 'pv10': 10, 'pv11': 11, 'pv12': 12, 'pv13': 13, 'pv14': 14,
                'pv15': 15, 'pv16': 16, 'pv17': 17, 'pv18': 18, 'pv19': 19, 'pv20': 20, 'pv21': 21,
                'pv22': 22, 'pv23': 23}

        def _do_command(api):
            return data

        master_communicator = Mock()
        master_communicator.do_command = _do_command

        SetUpTestInjections(master_communicator=master_communicator,
                            configuration_controller=Mock(),
                            eeprom_controller=Mock())
        SetUpTestInjections(master_controller=MasterClassicController(),
                            maintenance_controller=Mock())

        for i in range(24):
            PulseCounter(number=i, name='PulseCounter {0}'.format(i), source='master', persistent=False).save()

        controller = PulseCounterController()
        controller.set_amount_of_pulse_counters(26)
        controller.set_value(24, 123)
        controller.set_value(25, 456)

        values_dict = controller.get_values()
        values = [values_dict[i] for i in sorted(values_dict.keys())]
        self.assertEqual(list(range(0, 24)) + [123, 456], values)

        # Set pulse counter for unexisting pulse counter
        with self.assertRaises(DoesNotExist):
            controller.set_value(26, 789)

        # Set pulse counter for physical pulse counter
        with self.assertRaises(ValueError):
            controller.set_value(23, 789)

    def test_config(self):
        master_pulse_counters = {}

        def _save_pulse_counters(data):
            for dto, fields in data:
                master_pulse_counters[dto.id] = dto

        master_controller_mock = Mock()
        master_controller_mock.load_pulse_counter = lambda pulse_counter_id: master_pulse_counters[pulse_counter_id]
        master_controller_mock.save_pulse_counters = _save_pulse_counters

        SetUpTestInjections(master_controller=master_controller_mock,
                            maintenance_controller=Mock())
        controller = PulseCounterController()

        # Simulate master contents & initial sync
        for i in range(24):
            master_pulse_counters[i] = PulseCounterDTO(id=i, name=u'PulseCounter {0}'.format(i), persistent=False)
            PulseCounter(number=i, name='PulseCounter {0}'.format(i), source='master', persistent=False).save()

        controller.set_amount_of_pulse_counters(26)
        controller.save_pulse_counters([
            (PulseCounterDTO(id=1, name='Water', input_id=10, room=1), ['name', 'input', 'room']),
            (PulseCounterDTO(id=4, name='Gas', input_id=11, room=2), ['name', 'input', 'room']),
            (PulseCounterDTO(id=25, name='Electricity', input_id=None, room=3, persistent=True), ['name', 'input', 'room', 'persistent'])
        ])
        received_dtos = controller.load_pulse_counters()
        expected_dtos = [PulseCounterDTO(id=i, name=u'PulseCounter {0}'.format(i))
                         for i in range(26)]
        expected_dtos[1] = PulseCounterDTO(id=1, name='Water', input_id=10, room=1)
        expected_dtos[4] = PulseCounterDTO(id=4, name='Gas', input_id=11, room=2)
        expected_dtos[25] = PulseCounterDTO(id=25, name='Electricity', input_id=None, room=3, persistent=True)

        self.assertEqual(expected_dtos, received_dtos)

        # Try to set input on virtual pulse counter
        controller.save_pulse_counters([(PulseCounterDTO(id=25, name='Electricity', input_id=22, room=3), ['name', 'input_id'])])
        self.assertEqual(PulseCounterDTO(id=25, name='Electricity', room=3, persistent=True), controller.load_pulse_counter(25))

        # Get configuration for existing master pulse counter
        self.assertEqual(PulseCounterDTO(id=1, name='Water', input_id=10, room=1, persistent=False), controller.load_pulse_counter(1))

        # Get configuration for unexisting pulse counter
        with self.assertRaises(DoesNotExist):
            controller.save_pulse_counters([(PulseCounterDTO(id=26, name='Electricity'), ['name'])])

        # Set configuration for unexisting pulse counter
        with self.assertRaises(DoesNotExist):
            controller.load_pulse_counter(26)


if __name__ == '__main__':
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
