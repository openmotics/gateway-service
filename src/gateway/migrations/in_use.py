# Copyright (C) 2022 OpenMotics BV
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

import logging

from gateway.migrations.base_migrator import BaseMigrator
from gateway.models import Database, Output, Input, Shutter, ShutterGroup, PulseCounter, GroupAction
from ioc import INJECTED, Inject

if False:  # MYPY
    from gateway.hal.master_controller import MasterController
    from typing import Optional

logger = logging.getLogger(__name__)


class InUseMigrator(BaseMigrator):

    MIGRATION_KEY = 'in_use'

    @classmethod
    @Inject
    def _migrate(cls, master_controller=INJECTED):  # type: (MasterController) -> None
        with Database.get_session() as db:
            # Outputs & shutters
            for output_dto in master_controller.load_outputs():
                output_orm = db.query(Output).filter(Output.number == output_dto.id).one_or_none()  # type: Optional[Output]
                if output_orm is not None:
                    output_orm.in_use = output_orm.name.strip() not in ['', 'NOT_IN_USE']
                    if not output_orm.in_use:
                        output_orm.name = ''
            # Pulse Counters
            pulse_counters = master_controller.load_pulse_counters()
            for pulse_counter_dto in pulse_counters:
                pulse_counter_orm = db.query(PulseCounter).filter(PulseCounter.number == pulse_counter_dto.id).one_or_none()  # type: Optional[PulseCounter]
                if pulse_counter_orm is not None:
                    pulse_counter_orm.in_use = (pulse_counter_orm.name.strip() not in ['', 'NOT_IN_USE'] and
                                                pulse_counter_dto.input_id not in [None, 255])
                    if not pulse_counter_orm.in_use:
                        pulse_counter_orm.name = ''
            # Inputs
            used_pulse_counter_inputs = [pulse_counter.input_id for pulse_counter in pulse_counters
                                         if pulse_counter.input_id not in [None, 255]]
            for input_dto in master_controller.load_inputs():
                input_orm = db.query(Input).filter(Input.number == input_dto.id).one_or_none()  # type: Optional[Input]
                if input_orm is not None:
                    input_orm.in_use = ((input_dto.id in used_pulse_counter_inputs or
                                         input_dto.action != 255) and
                                        input_orm.name.strip() not in ['', 'NOT_IN_U', 'NOT_IN_USE'])
                    if not input_orm.in_use:
                        input_orm.name = ''
            # Shutters
            shutters = master_controller.load_shutters()
            for shutter_dto in shutters:
                shutter_orm = db.query(Shutter).filter(Shutter.number == shutter_dto.id).one_or_none()  # type: Optional[Shutter]
                if shutter_orm is not None:
                    shutter_orm.in_use = shutter_orm.name.strip() not in ['', 'NOT_IN_USE']
                    if not shutter_orm.in_use:
                        shutter_orm.name = ''
            # Shutter groups
            used_shutter_groups = list(set([shutter_dto.group_1 for shutter_dto in shutters
                                            if shutter_dto.group_1 not in [None, 255]] +
                                           [shutter_dto.group_2 for shutter_dto in shutters
                                            if shutter_dto.group_2 not in [None, 255]]))
            for shutter_group_dto in master_controller.load_shutter_groups():
                shutter_group_orm = db.query(ShutterGroup).filter(ShutterGroup.number == shutter_group_dto.id).one_or_none()  # type: Optional[ShutterGroup]
                if shutter_group_orm is not None:
                    shutter_group_orm.in_use = shutter_group_orm.number in used_shutter_groups
            # Sensors: Not needed, as all currently sensors in the ORM should be in use
            db.commit()
