# Copyright (C) 2020 OpenMotics BV
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

from gateway.dto import OutputDTO, OutputStateDTO
from gateway.hal.master_controller import MasterController
from gateway.maintenance_controller import MaintenanceController
from gateway.models import Output, Room
from gateway.output_controller import OutputController
from ioc import SetTestMode, SetUpTestInjections


class OutputControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.master_controller = mock.Mock(MasterController)
        SetUpTestInjections(maintenance_controller=mock.Mock(MaintenanceController),
                            master_controller=self.master_controller)
        self.controller = OutputController()

    def test_get_output_status(self):
        with mock.patch.object(self.master_controller, 'get_output_status',
                               return_value=OutputStateDTO(id=42)):
            status = self.controller.get_output_status(42)
            assert status == OutputStateDTO(id=42)

    def test_get_output_statuses(self):
        with mock.patch.object(self.master_controller, 'get_output_statuses',
                               return_value=[OutputStateDTO(id=42)]):
            status = self.controller.get_output_statuses()
            assert len(status) == 1
            assert OutputStateDTO(id=42) in status

    def test_load_output(self):
        with mock.patch.object(Output, 'get', return_value=Output(id=1, number=42, room=Room(id=2, number=3))), \
             mock.patch.object(self.master_controller, 'load_output',
                               return_value=OutputDTO(id=42)) as load:
            output = self.controller.load_output(42)
            assert output == OutputDTO(id=42, room=3)
            load.assert_called_with(output_id=42)

    def test_load_outputs(self):
        with mock.patch.object(Output, 'select', return_value=[Output(id=1, number=42, room=Room(id=2, number=3))]), \
             mock.patch.object(self.master_controller, 'load_output',
                               return_value=OutputDTO(id=42)) as load:
            outputs = self.controller.load_outputs()
            assert OutputDTO(id=42, room=3) in outputs
            load.assert_called_with(output_id=42)
