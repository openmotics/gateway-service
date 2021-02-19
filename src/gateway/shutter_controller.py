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
"""
This module contains logic to handle shutters with their state/position
"""
from __future__ import absolute_import

import logging
import time
from threading import Lock
from peewee import JOIN
from gateway.base_controller import BaseController, SyncStructure
from gateway.dto import ShutterDTO, ShutterGroupDTO
from gateway.enums import ShutterEnums
from gateway.events import GatewayEvent
from gateway.hal.master_event import MasterEvent
from gateway.models import Room, Shutter, ShutterGroup
from gateway.pubsub import PubSub
from ioc import INJECTED, Inject, Injectable, Singleton
from toolbox import Toolbox

if False:  # MYPY
    from typing import List, Dict, Optional, Tuple, Any
    from gateway.hal.master_controller import MasterController

logger = logging.getLogger('openmotics')


@Injectable.named('shutter_controller')
@Singleton
class ShutterController(BaseController):
    """
    Controls everything related to shutters.

    Important assumptions:
    * A shutter can go UP and go DOWN
    * A shutter that is UP is considered open and has a position of 0
    * A shutter that is DOWN is considered closed and has a position of `steps`

    # TODO: The states OPEN and CLOSED make more sense but is a reasonable heavy change at this moment. To be updated if/when a new Gateway API is introduced
    """

    SYNC_STRUCTURES = [SyncStructure(Shutter, 'shutter'),
                       SyncStructure(ShutterGroup, 'shutter_group')]
    DIRECTION_STATE_MAP = {ShutterEnums.Direction.UP: ShutterEnums.State.GOING_UP,
                           ShutterEnums.Direction.DOWN: ShutterEnums.State.GOING_DOWN,
                           ShutterEnums.Direction.STOP: ShutterEnums.State.STOPPED}
    DIRECTION_END_STATE_MAP = {ShutterEnums.Direction.UP: ShutterEnums.State.UP,
                               ShutterEnums.Direction.DOWN: ShutterEnums.State.DOWN,
                               ShutterEnums.Direction.STOP: ShutterEnums.State.STOPPED}
    STATE_DIRECTION_MAP = {ShutterEnums.State.GOING_UP: ShutterEnums.Direction.UP,
                           ShutterEnums.State.GOING_DOWN: ShutterEnums.Direction.DOWN,
                           ShutterEnums.State.STOPPED: ShutterEnums.Direction.STOP}

    TIME_BASED_SHUTTER_STEPS = 100
    SINGLE_ACTION_ACCURACY_LOSS_PERCENTAGE = 10

    @Inject
    def __init__(self, master_controller=INJECTED, verbose=False):  # type: (MasterController, bool) -> None
        super(ShutterController, self).__init__(master_controller)

        self._shutters = {}  # type: Dict[int, ShutterDTO]
        self._actual_positions = {}  # type: Dict[int, Optional[int]]
        self._desired_positions = {}  # type: Dict[int, Optional[int]]
        self._directions = {}  # type: Dict[int, str]
        self._states = {}  # type: Dict[int, Tuple[float, str]]
        self._position_accuracy = {}  # type: Dict[int, float]

        self._verbose = verbose
        self._config_lock = Lock()

        self._pubsub.subscribe_master_events(PubSub.MasterTopics.SHUTTER, self._handle_master_event)

    def _log(self, message):  # type: (str) -> None
        if self._verbose:
            logger.info('ShutterController: {0}'.format(message))

    # Update internal shutter configuration cache

    def _handle_master_event(self, event):  # type: (MasterEvent) -> None
        super(ShutterController, self)._handle_master_event(event)
        if event.type == MasterEvent.Types.SHUTTER_CHANGE:
            self._report_shutter_state(event.data['id'], event.data['status'])

    def _sync_orm(self):
        super(ShutterController, self)._sync_orm()
        self.update_config(self.load_shutters())

    def update_config(self, config):  # type: (List[ShutterDTO]) -> None
        with self._config_lock:
            shutter_ids = []
            for shutter_dto in config:
                shutter_id = shutter_dto.id
                shutter_ids.append(shutter_id)
                if shutter_dto != self._shutters.get(shutter_id):
                    self._shutters[shutter_id] = shutter_dto
                    self._states[shutter_id] = (0.0, ShutterEnums.State.STOPPED)
                    self._actual_positions[shutter_id] = None
                    self._desired_positions[shutter_id] = None
                    self._directions[shutter_id] = ShutterEnums.Direction.STOP
                    self._position_accuracy[shutter_id] = 100 if shutter_dto.steps else 0

            for shutter_id in list(self._shutters.keys()):
                if shutter_id not in shutter_ids:
                    del self._shutters[shutter_id]
                    del self._states[shutter_id]
                    del self._actual_positions[shutter_id]
                    del self._desired_positions[shutter_id]
                    del self._directions[shutter_id]
                    del self._position_accuracy[shutter_id]

    # Allow shutter positions to be reported

    def report_shutter_position(self, shutter_id, position, direction=None):
        # type: (int, int, Optional[str]) -> None
        self._log('Shutter {0} reports position {1}'.format(shutter_id, position))
        # Fetch and validate information
        shutter = self._get_shutter(shutter_id)
        steps = ShutterController._get_steps(shutter)
        ShutterController._validate_position(shutter_id, position, steps)

        # Store new position
        self._actual_positions[shutter_id] = position

        # Update the direction and report if changed
        expected_direction = self._directions[shutter_id]
        if direction is not None and expected_direction != direction:
            # We received a more accurate direction
            self._log('Shutter {0} report direction change to {1}'.format(shutter_id, direction))
            self._report_shutter_state(shutter_id, ShutterController.DIRECTION_STATE_MAP[direction])

        direction = self._directions[shutter_id]
        desired_position = self._desired_positions[shutter_id]
        if desired_position is None:
            return
        if ShutterController._is_position_reached(direction, desired_position, position, stopped=True):
            self._log('Shutter {0} reported position is desired position: Stopping'.format(shutter_id))
            self.shutter_stop(shutter_id)

    def report_shutter_lost_position(self, shutter_id):  # type: (int) -> None
        self._log('Shutter {0} reports lost position')

        # Clear position & force report
        self._actual_positions[shutter_id] = None
        self._report_shutter_state(shutter_id, ShutterEnums.State.STOPPED, force_report=True)

    # Configure shutters

    def load_shutter(self, shutter_id):  # type: (int) -> ShutterDTO
        shutter = Shutter.select(Room) \
                         .join_from(Shutter, Room, join_type=JOIN.LEFT_OUTER) \
                         .where(Shutter.number == shutter_id) \
                         .get()  # type: Shutter
        shutter_dto = self._master_controller.load_shutter(shutter_id=shutter_id)  # TODO: Load dict
        shutter_dto.room = shutter.room.number if shutter.room is not None else None
        return shutter_dto

    def load_shutters(self):  # type: () -> List[ShutterDTO]
        shutter_dtos = []
        for shutter in list(Shutter.select(Shutter, Room)
                                   .join_from(Shutter, Room, join_type=JOIN.LEFT_OUTER)):  # TODO: Load dicts
            shutter_dto = self._master_controller.load_shutter(shutter_id=shutter.number)
            shutter_dto.room = shutter.room.number if shutter.room is not None else None
            shutter_dtos.append(shutter_dto)
        return shutter_dtos

    def save_shutters(self, shutters):  # type: (List[Tuple[ShutterDTO, List[str]]]) -> None
        shutters_to_save = []
        for shutter_dto, fields in shutters:
            shutter = Shutter.get_or_none(number=shutter_dto.id)  # type: Shutter
            if shutter is None:
                logger.info('Ignored saving non-existing Shutter {0}'.format(shutter_dto.id))
            if 'room' in fields:
                if shutter_dto.room is None:
                    shutter.room = None
                elif 0 <= shutter_dto.room <= 100:
                    shutter.room, _ = Room.get_or_create(number=shutter_dto.room)
                shutter.save()
            shutters_to_save.append((shutter_dto, fields))
        self._master_controller.save_shutters(shutters_to_save)
        self.update_config(self.load_shutters())

    def load_shutter_group(self, group_id):  # type: (int) -> ShutterGroupDTO
        shutter_group = ShutterGroup.select(Room) \
                                    .join_from(ShutterGroup, Room, join_type=JOIN.LEFT_OUTER) \
                                    .where(ShutterGroup.number == group_id) \
                                    .get()  # type: ShutterGroup
        shutter_group_dto = self._master_controller.load_shutter_group(shutter_group_id=group_id)  # TODO: Load dict
        shutter_group_dto.room = shutter_group.room.number if shutter_group.room is not None else None
        return shutter_group_dto

    def load_shutter_groups(self):  # type: () -> List[ShutterGroupDTO]
        shutter_group_dtos = []
        for shutter_group in list(ShutterGroup.select(ShutterGroup, Room)
                                              .join_from(ShutterGroup, Room, join_type=JOIN.LEFT_OUTER)):  # TODO: Load dicts
            shutter_group_dto = self._master_controller.load_shutter_group(shutter_group_id=shutter_group.number)
            shutter_group_dto.room = shutter_group.room.number if shutter_group.room is not None else None
            shutter_group_dtos.append(shutter_group_dto)
        return shutter_group_dtos

    def save_shutter_groups(self, shutter_groups):  # type: (List[Tuple[ShutterGroupDTO, List[str]]]) -> None
        shutter_groups_to_save = []
        for shutter_group_dto, fields in shutter_groups:
            shutter_group = ShutterGroup.get_or_none(number=shutter_group_dto.id)  # type: ShutterGroup
            if shutter_group is None:
                continue
            if 'room' in fields:
                if shutter_group_dto.room is None:
                    shutter_group.room = None
                elif 0 <= shutter_group_dto.room <= 100:
                    shutter_group.room, _ = Room.get_or_create(number=shutter_group_dto.room)
                shutter_group.save()
            shutter_groups_to_save.append((shutter_group_dto, fields))
        self._master_controller.save_shutter_groups(shutter_groups_to_save)

    # Control shutters

    def shutter_group_down(self, group_id):  # type: (int) -> None
        self._master_controller.shutter_group_down(group_id)

    def shutter_group_up(self, group_id):  # type: (int) -> None
        self._master_controller.shutter_group_up(group_id)

    def shutter_group_stop(self, group_id):  # type: (int) -> None
        self._master_controller.shutter_group_stop(group_id)

    def shutter_up(self, shutter_id, desired_position=None):  # type: (int, Optional[int]) -> None
        return self._shutter_goto_direction(shutter_id, ShutterEnums.Direction.UP, desired_position)

    def shutter_down(self, shutter_id, desired_position=None):  # type: (int, Optional[int]) -> None
        return self._shutter_goto_direction(shutter_id, ShutterEnums.Direction.DOWN, desired_position)

    def shutter_goto(self, shutter_id, desired_position):  # type: (int, int) -> None
        # Fetch and validate data
        shutter = self._get_shutter(shutter_id)
        steps = ShutterController._get_steps(shutter)
        timer = None

        if steps is None:
            ShutterController._validate_position(shutter_id, desired_position, self.TIME_BASED_SHUTTER_STEPS)
            timer = self._calculate_shutter_timer(shutter_id, desired_position)
        else:
            ShutterController._validate_position(shutter_id, desired_position, steps)

        actual_position = self._actual_positions.get(shutter_id)
        if actual_position is None:
            raise RuntimeError('Shutter {0} has unknown actual position'.format(shutter_id))

        direction = self._get_direction(actual_position, desired_position)
        if direction == ShutterEnums.Direction.STOP:
            return self.shutter_stop(shutter_id)

        self._log('Shutter {0} setting desired position to {1}'.format(shutter_id, desired_position))

        self._desired_positions[shutter_id] = desired_position
        self._directions[shutter_id] = direction
        self._execute_shutter(shutter_id, direction, timer=timer)

    def shutter_stop(self, shutter_id):  # type: (int) -> None
        # Validate data
        self._get_shutter(shutter_id)

        self._log('Shutter {0} stopped. Removing desired position'.format(shutter_id))

        self._desired_positions[shutter_id] = None
        self._directions[shutter_id] = ShutterEnums.Direction.STOP
        self._execute_shutter(shutter_id, ShutterEnums.Direction.STOP)

    # Control operations

    def _shutter_goto_direction(self, shutter_id, direction, desired_position=None):
        # type: (int, str, Optional[int]) -> None
        # Fetch and validate data
        timer = None
        shutter = self._get_shutter(shutter_id)
        steps = ShutterController._get_steps(shutter)

        if desired_position is None:
            if steps is None:
                desired_position = ShutterController._get_limit(direction, self.TIME_BASED_SHUTTER_STEPS)
            else:
                desired_position = ShutterController._get_limit(direction, steps)
        else:
            if steps is None:
                # we use a percentage (steps=100) to mimic the steps
                timer = self._calculate_shutter_timer(shutter_id, desired_position)
            else:
                ShutterController._validate_position(shutter_id, desired_position, steps)

        self._log('Shutter {0} setting direction to {1} {2}'.format(
            shutter_id, direction,
            'without position' if desired_position is None else 'with position {0}'.format(desired_position)
        ))

        self._desired_positions[shutter_id] = desired_position
        self._directions[shutter_id] = direction
        self._execute_shutter(shutter_id, direction, timer=timer)

    def _calculate_shutter_timer(self, shutter_id, desired_position, steps=TIME_BASED_SHUTTER_STEPS):
        ShutterController._validate_position(shutter_id, desired_position, steps)
        actual_position = self._actual_positions.get(shutter_id)
        if actual_position is None or self._position_accuracy[shutter_id] <= 0:
            self.reset_shutter(shutter_id)
            actual_position = self._actual_positions.get(shutter_id)
            if actual_position is None:
                raise RuntimeError('Shutter {0} has unknown actual position'.format(shutter_id))
            if self._position_accuracy[shutter_id] <= 0:
                raise RuntimeError('Could not get accurate position for shutter {}'.format(shutter_id))
        ShutterController._validate_position(shutter_id, desired_position, steps)
        shutter = self._get_shutter(shutter_id)
        delta_position = desired_position - actual_position
        direction = self._get_direction(actual_position, desired_position)
        if direction == ShutterEnums.Direction.STOP:
            return 0
        else:
            configured_timer = getattr(shutter, 'timer_{0}'.format(direction.lower()))
            return int(abs(delta_position) / float(steps) * configured_timer)

    def _execute_shutter(self, shutter_id, direction, timer=None):  # type: (int, str, Optional[int]) -> None
        logger.debug('_execute_shutter({}, {}, timer={}'.format(shutter_id, direction, timer))
        if direction == ShutterEnums.Direction.STOP or timer == 0:
            self._master_controller.shutter_stop(shutter_id)
        else:
            if direction == ShutterEnums.Direction.UP:
                self._master_controller.shutter_up(shutter_id, timer=timer)
            elif direction == ShutterEnums.Direction.DOWN:
                self._master_controller.shutter_down(shutter_id, timer=timer)

    def reset_shutter(self, shutter_id):  # type: (int) -> None
        # reset shutter to known state
        logger.debug('resetting shutter {}...'.format(shutter_id))
        shutter = self._get_shutter(shutter_id)
        configured_timer = getattr(shutter, 'timer_up')
        start = time.time()
        self._execute_shutter(shutter_id, ShutterEnums.Direction.UP)
        # TODO: https://openmotics.atlassian.net/browse/OM-2026
        while self._actual_positions[shutter_id] != 0:
            if time.time() - start > configured_timer * 1.1:
                raise RuntimeError('Timer expired when resetting shutter, could not get actual position')
            time.sleep(1)
        self._position_accuracy[shutter_id] = 100
        logger.info('shutter {} reset complete'.format(shutter_id))

    # Internal checks and validators

    def _get_shutter(self, shutter_id, return_none=False):  # type: (int, bool) -> Optional[ShutterDTO]
        shutter = self._shutters.get(shutter_id)
        if shutter is None:
            self.update_config(self.load_shutters())
            shutter = self._shutters.get(shutter_id)
            if shutter is None and return_none is False:
                raise RuntimeError('Shutter {0} is not available'.format(shutter_id))
        return shutter

    @staticmethod
    def _is_position_reached(direction, desired_position, actual_position, stopped=True):
        # type: (str, int, int, bool) -> bool
        if desired_position == actual_position:
            return True  # Obviously reached
        if direction == ShutterEnums.Direction.STOP:
            return stopped  # Can't be decided, so return user value
        # An overshoot is considered as "position reached"
        if direction == ShutterEnums.Direction.UP:
            return actual_position < desired_position
        return actual_position > desired_position

    @staticmethod
    def _get_limit(direction, steps):  # type: (str, Optional[int]) -> Optional[int]
        if steps is None:
            return None
        if direction == ShutterEnums.Direction.UP:
            return 0
        return steps - 1

    @staticmethod
    def _get_direction(actual_position, desired_position):  # type: (int, int) -> str
        if actual_position == desired_position:
            return ShutterEnums.Direction.STOP
        if actual_position < desired_position:
            return ShutterEnums.Direction.UP
        return ShutterEnums.Direction.DOWN

    @staticmethod
    def _get_steps(shutter):  # type: (ShutterDTO) -> Optional[int]
        steps = shutter.steps
        if steps in [0, 1, None]:
            # These step values are considered "not configured" and thus "no position support"
            return None
        return steps

    @staticmethod
    def clamp_position(shutter, position):  # type: (ShutterDTO, int) -> int
        steps = ShutterController._get_steps(shutter)
        max_position = steps - 1 if steps is not None else ShutterController.TIME_BASED_SHUTTER_STEPS - 1
        return max(0, min(position, max_position))

    @staticmethod
    def _validate_position(shutter_id, position, steps):  # type: (int, int, Optional[int]) -> None
        if steps is None:
            raise RuntimeError('Shutter {0} does not support positioning'.format(shutter_id))
        if not (0 <= position < steps):
            raise RuntimeError('Shutter {0} has a position limit of 0 <= position <= {1}'.format(shutter_id, steps - 1))

    # Reporting

    def _report_shutter_state(self, shutter_id, new_state, force_report=False):
        # type: (int, str, bool) -> None
        shutter = self._get_shutter(shutter_id, return_none=True)
        if shutter is None:
            logger.warning('Shutter {0} unknown'.format(shutter_id))
            return
        steps = ShutterController._get_steps(shutter)

        self._directions[shutter_id] = ShutterController.STATE_DIRECTION_MAP[new_state]
        self._log('Shutter {0} reports state {1}, which is direction {2}'.format(shutter_id, new_state, self._directions[shutter_id]))

        current_state_timestamp, current_state = self._states[shutter_id]
        if new_state == current_state or (new_state == ShutterEnums.State.STOPPED and current_state in [ShutterEnums.State.DOWN, ShutterEnums.State.UP]):
            if force_report:
                self._log('Shutter {0} force reported new state {1}'.format(shutter_id, new_state))
                self._states[shutter_id] = (time.time(), new_state)
                self._publish_shutter_change(shutter_id, shutter, self._states[shutter_id])
            else:
                self._log('Shutter {0} new state {1} ignored since it equals {2}'.format(shutter_id, new_state, current_state))
            return  # State didn't change, nothing to do

        if new_state != ShutterEnums.State.STOPPED:
            # Shutter started moving
            self._states[shutter_id] = (time.time(), new_state)
            self._log('Shutter {0} started moving'.format(shutter_id))
        else:
            direction = ShutterController.STATE_DIRECTION_MAP[current_state]
            if steps is None:
                # Time based state calculation
                timer = getattr(shutter, 'timer_{0}'.format(direction.lower()))
                if timer is None:
                    self._log('Shutter {0} is time-based but has no valid timer. New state {1}'.format(shutter_id, ShutterEnums.State.STOPPED))
                    new_state = ShutterEnums.State.STOPPED
                else:
                    elapsed_time = time.time() - current_state_timestamp
                    threshold_timer = 0.95 * timer  # Allow 5% difference
                    if elapsed_time >= threshold_timer:  # The shutter was going up/down for the whole `timer`. So it's now up/down
                        self._log('Shutter {0} going {1} passed time threshold. New state {2}'.format(shutter_id, direction, ShutterController.DIRECTION_END_STATE_MAP[direction]))
                        new_state = ShutterController.DIRECTION_END_STATE_MAP[direction]
                        direction_to_check = ShutterEnums.Direction.UP if not shutter.up_down_config else ShutterEnums.Direction.DOWN
                        new_actual_position = 0 if direction == direction_to_check else self.TIME_BASED_SHUTTER_STEPS - 1
                        self._actual_positions[shutter_id] = ShutterController.clamp_position(shutter, new_actual_position)
                        self._position_accuracy[shutter_id] = 100
                    else:
                        new_state = ShutterEnums.State.STOPPED
                        abs_position_delta = elapsed_time / float(timer) * self.TIME_BASED_SHUTTER_STEPS
                        position_delta = -abs_position_delta if direction == ShutterEnums.Direction.UP else abs_position_delta
                        if shutter.up_down_config:
                            position_delta = -position_delta
                        actual_position = self._actual_positions[shutter_id]
                        if actual_position is not None:
                            new_actual_position = actual_position + int(position_delta)
                            self._actual_positions[shutter_id] = ShutterController.clamp_position(shutter, new_actual_position)
                            self._position_accuracy[shutter_id] = self._position_accuracy.get(shutter_id, 0) - self.SINGLE_ACTION_ACCURACY_LOSS_PERCENTAGE
                        else:
                            self._position_accuracy[shutter_id] = 0
                        self._log('Shutter {0} going {1} for {2:.2f}% ({3:.2f}s - timer: {4:.2f}s). New state {5}.'
                                  'Actual position: {6}. Position accuracy: {7}'.format(shutter_id, direction,
                                                                                        abs_position_delta, elapsed_time,
                                                                                        threshold_timer, new_state,
                                                                                        self._actual_positions[shutter_id],
                                                                                        self._position_accuracy[shutter_id]))
            else:
                # Supports position, so state will be calculated on position
                limit_position = ShutterController._get_limit(direction, steps)
                if ShutterController._is_position_reached(direction, limit_position, self._actual_positions[shutter_id]):
                    self._log('Shutter {0} going {1} reached limit. New state {2}'.format(shutter_id, direction, ShutterController.DIRECTION_END_STATE_MAP[direction]))
                    new_state = ShutterController.DIRECTION_END_STATE_MAP[direction]
                else:
                    self._log('Shutter {0} going {1} did not reach limit. New state {2}'.format(shutter_id, direction, ShutterEnums.State.STOPPED))
                    new_state = ShutterEnums.State.STOPPED

            self._states[shutter_id] = (time.time(), new_state)

        self._publish_shutter_change(shutter_id, shutter, self._states[shutter_id])

    def get_states(self):  # type: () -> Dict[str, Any]
        all_states = []
        for i in sorted(self._states.keys()):
            all_states.append(self._states[i][1])
        return {'status': all_states,
                'detail': {shutter_id: {'state': self._states[shutter_id][1],
                                        'actual_position': self._actual_positions[shutter_id],
                                        'desired_position': self._desired_positions[shutter_id],
                                        'last_change': self._states[shutter_id][0]}
                           for shutter_id in self._shutters}}

    def _publish_shutter_change(self, shutter_id, shutter_data, shutter_state):  # type: (int, ShutterDTO, Tuple[float, str]) -> None
        gateway_event = GatewayEvent(event_type=GatewayEvent.Types.SHUTTER_CHANGE,
                                     data={'id': shutter_id,
                                           'status': {'state': shutter_state[1].upper(),
                                                      'position': self._actual_positions.get(shutter_id),
                                                      'last_change': shutter_state[0]},
                                           'location': {'room_id': Toolbox.nonify(shutter_data.room, 255)}})
        self._pubsub.publish_gateway_event(PubSub.GatewayTopics.STATE, gateway_event)
