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
Tests for the outputs module.
"""

from __future__ import absolute_import
import unittest
import xmlrunner

from master.classic.outputs import OutputStatus
from gateway.dto import OutputStateDTO


class OutputStatusTest(unittest.TestCase):
    """ Tests for OutputStatus. """

    def test_update(self):
        """ Test for partial_update and full_update"""
        events = []
        status = OutputStatus(on_output_change=lambda output_id, state: events.append((output_id, state)))

        events = []
        status.full_update([{'id': 1, 'ctimer': 200, 'status': 1, 'dimmer': 10},
                            {'id': 2, 'ctimer': 200, 'status': 0, 'dimmer': 20},
                            {'id': 3, 'ctimer': 200, 'status': 0, 'dimmer': 0}])
        current_state = status.get_outputs()
        self.assertEqual([OutputStateDTO(id=1, ctimer=200, status=True, dimmer=10, locked=False),
                          OutputStateDTO(id=2, ctimer=200, status=False, dimmer=20, locked=False),
                          OutputStateDTO(id=3, ctimer=200, status=False, dimmer=0, locked=False)],
                         [x for x in sorted(current_state, key=lambda i: i.id)])
        self.assertEqual([(1, {'on': True, 'value': 10, 'locked': False}),
                          (2, {'on': False, 'value': 20, 'locked': False}),
                          (3, {'on': False, 'value': 0, 'locked': False})], sorted(events, key=lambda i: i[0]))

        events = []
        status.partial_update([])  # Everything is off
        current_state = status.get_outputs()
        self.assertEqual([OutputStateDTO(id=1, ctimer=200, status=False, dimmer=10, locked=False),
                          OutputStateDTO(id=2, ctimer=200, status=False, dimmer=20, locked=False),
                          OutputStateDTO(id=3, ctimer=200, status=False, dimmer=0, locked=False)],
                         sorted(current_state, key=lambda i: i.id))
        self.assertEqual([(1, {'on': False, 'value': 10, 'locked': False})], sorted(events, key=lambda i: i[0]))

        events = []
        status.partial_update([(3, 0), (2, 10)])  # Turn two outputs on
        current_state = status.get_outputs()
        self.assertEqual([OutputStateDTO(id=1, ctimer=200, status=False, dimmer=10, locked=False),
                          OutputStateDTO(id=2, ctimer=200, status=True, dimmer=10, locked=False),
                          OutputStateDTO(id=3, ctimer=200, status=True, dimmer=0, locked=False)],
                         sorted(current_state, key=lambda i: i.id))
        self.assertEqual([(2, {'on': True, 'value': 10, 'locked': False}),
                          (3, {'on': True, 'value': 0, 'locked': False})], sorted(events, key=lambda i: i[0]))

        events = []
        status.partial_update([(3, 0)])  # Turn one output off again
        current_state = status.get_outputs()
        self.assertEqual([OutputStateDTO(id=1, ctimer=200, status=False, dimmer=10, locked=False),
                          OutputStateDTO(id=2, ctimer=200, status=False, dimmer=10, locked=False),
                          OutputStateDTO(id=3, ctimer=200, status=True, dimmer=0, locked=False)],
                         sorted(current_state, key=lambda i: i.id))
        self.assertEqual([(2, {'on': False, 'value': 10, 'locked': False})], sorted(events, key=lambda i: i[0]))

        events = []
        status.update_locked(1, True)
        current_state = status.get_outputs()
        self.assertEqual([OutputStateDTO(id=1, ctimer=200, status=False, dimmer=10, locked=True),
                          OutputStateDTO(id=2, ctimer=200, status=False, dimmer=10, locked=False),
                          OutputStateDTO(id=3, ctimer=200, status=True, dimmer=0, locked=False)],
                         sorted(current_state, key=lambda i: i.id))
        self.assertEqual([(1, {'on': False, 'value': 10, 'locked': True})], sorted(events, key=lambda i: i[0]))

        events = []
        status.partial_update([(2, 50)])  # Turn one off and another one on
        current_state = status.get_outputs()
        self.assertEqual([OutputStateDTO(id=1, ctimer=200, status=False, dimmer=10, locked=True),
                          OutputStateDTO(id=2, ctimer=200, status=True, dimmer=50, locked=False),
                          OutputStateDTO(id=3, ctimer=200, status=False, dimmer=0, locked=False)],
                         sorted(current_state, key=lambda i: i.id))
        self.assertEqual([(2, {'on': True, 'value': 50, 'locked': False}),
                          (3, {'on': False, 'value': 0, 'locked': False})], sorted(events, key=lambda i: i[0]))

        events = []
        status.full_update([{'id': 1, 'ctimer': 200, 'status': 1, 'dimmer': 10},
                            {'id': 2, 'ctimer': 200, 'status': 0, 'dimmer': 20},
                            {'id': 4, 'ctimer': 200, 'status': 1, 'dimmer': 40}])
        current_state = status.get_outputs()
        self.assertEqual([OutputStateDTO(id=1, ctimer=200, status=True, dimmer=10, locked=True),
                          OutputStateDTO(id=2, ctimer=200, status=False, dimmer=20, locked=False),
                          OutputStateDTO(id=4, ctimer=200, status=True, dimmer=40, locked=False)],
                         sorted(current_state, key=lambda i: i.id))
        self.assertEqual([(1, {'on': True, 'value': 10, 'locked': True}),
                          (2, {'on': False, 'value': 20, 'locked': False}),
                          (4, {'on': True, 'value': 40, 'locked': False})], sorted(events, key=lambda i: i[0]))


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
