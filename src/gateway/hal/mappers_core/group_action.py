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

"""
GroupAction Mapper
"""
from __future__ import absolute_import
from gateway.dto import GroupActionDTO
from master.core.group_action import GroupAction
from master.core.basic_action import BasicAction

if False:  # MYPY
    from typing import List, Dict, Any, Optional


class GroupActionMapper(object):
    BYTE_MAX = 255

    @staticmethod
    def orm_to_dto(orm_object):  # type: (GroupAction) -> GroupActionDTO
        return GroupActionDTO(id=orm_object.id,
                              name=orm_object.name,
                              actions=GroupActionMapper.core_actions_to_classic_actions(orm_object.actions))

    @staticmethod
    def dto_to_orm(group_action_dto):  # type: (GroupActionDTO) -> GroupAction
        data = {'id': group_action_dto.id}  # type: Dict[str, Any]
        for dto_field, data_field in {'name': 'name'}.items():
            if dto_field in group_action_dto.loaded_fields:
                data[data_field] = getattr(group_action_dto, dto_field)
        if 'actions' in group_action_dto.loaded_fields:
            data['actions'] = GroupActionMapper.classic_actions_to_core_actions(group_action_dto.actions)
        return GroupAction(**data)

    @staticmethod
    def core_actions_to_classic_actions(actions):  # type: (List[BasicAction]) -> List[int]
        classic_actions = []
        for action in actions:
            # This mapping is based on the comments in the function below, since mapping back often only makes sense
            # for calls that can be mapped forward as well. It has some extras though.
            if action.action_type == 19:
                if action.action == 0:
                    classic_actions += [2, action.device_nr]
            elif action.action_type == 1:
                if action.action == 0:
                    classic_actions += [68, action.device_nr]
                elif action.action == 1:
                    classic_actions += [69, action.device_nr]
            elif action.action_type == 253:
                if action.action == 0:
                    classic_actions += [72, 255]
                elif action.action == 1:
                    classic_actions += [75 if action.device_nr else 76, 255]
            elif action.action_type == 10:
                if 0 <= action.action <= 5:
                    classic_actions += [{0: 102, 1: 100, 2: 101, 3: 108, 4: 109, 5: 103}[action.action], action.device_nr]
            elif action.action_type == 0:
                if action.action in [0, 1, 16]:
                    classic_actions += [{0: 160, 1: 161, 16: 162}[action.action], action.device_nr]
                elif action.action == 255:
                    classic_actions += [163 if action.device_nr == 1 else 164, 255]
                elif action.action == 9:
                    classic_actions += [169 if action.extra_parameter == 1 else 170, action.device_nr]
                map_0 = {2: {1: 165, 25: 176, 51: 177, 76: 178, 102: 179, 127: 180, 153: 181, 178: 182, 204: 183, 229: 184, 255: 166},
                         4: {150: 195, 450: 196, 900: 197, 1500: 198, 2220: 199, 3120: 200},
                         7: {150: 201, 450: 202, 900: 203, 1500: 204, 2220: 205, 3120: 206},
                         17: {25: 185, 51: 186, 76: 187, 102: 188, 127: 189, 153: 190, 178: 191, 204: 192, 229: 193, 255: 194}}  # type: Dict[int, Dict[int, int]]
                if action.action in map_0:
                    value = None  # type: Optional[int]
                    for key in sorted(list(map_0[action.action].keys())):
                        if action.extra_parameter >= key:
                            value = map_0[action.action][key]
                    if value is not None:
                        classic_actions += [value, action.device_nr]
            elif action.action_type == 100:
                map_100_0 = {0: 0, 90: 1, 91: 2, 150: 10, 200: 20, 255: 255}
                map_100_1 = {10: 243, 11: 244, 12: 241, 13: 242, 14: 245, 15: 246}
                if action.action in map_100_0:
                    classic_actions += [240, map_100_0[action.action]]
                elif action.action in map_100_1:
                    classic_actions += [map_100_1[action.action], action.device_nr]
            elif action.action_type == 254:
                if action.action == 0:
                    classic_actions += [254, 255]
        return classic_actions

    @staticmethod
    def classic_actions_to_core_actions(classic_actions):  # type: (List[int]) -> List[BasicAction]
        if len(classic_actions) % 2 != 0:
            raise ValueError('Classic actions must be a multiple of two')
        actions = []
        for i in range(0, len(classic_actions), 2):
            action_type = classic_actions[i]
            action_number = classic_actions[i + 1]
            #   0: Simple Action (Old instruction set, please do not use anymore)
            #   1: Simple Decision, ignore THEN/ELSE action, ignore previous decision (Old instruction set, please do not use anymore)
            if action_type == 2:
                #   2: Execute Group Action
                actions.append(BasicAction(action_type=19, action=0, device_nr=action_number))
            #   3: Put this Scheduled Action in the scheduled action queue
            #   4: Used by the system (to indicate in the queue which input has triggered the actions in the queue)
            #   7: Remove this Scheduled Action from the Scheduled action queue
            #   9: Simple Decision, perform THEN/ELSE action, ignore previous decision (Old instruction set, please do not use anymore)
            #  17: Simple Decision, ignore THEN/ELSE action, perform "OR" with previous decision (Old instruction set, please do not use anymore)
            #  25: Simple Decision, perform THEN/ELSE action, perform "OR" with previous decision (Old instruction set, please do not use anymore)
            #  49: Simple Decision, ignore THEN/ELSE action, perform "AND" with previous decision (Old instruction set, please do not use anymore)
            #  57: Simple Decision, perform THEN/ELSE action, perform "AND" with previous decision (Old instruction set, please do not use anymore)
            #  60: Will sent Event (API instruction EV) to the Beagle Bone Black and RTI RS232 port (when enabled) with Event Code x
            #  64: x=0 Put all Modules in lower power state (switch off leds except power and status led), x=1 Normal power state, x=2 normal power state for 2 minutes
            #  65: Flash led of output x
            #  66: Flash led of input x
            #  67: Flash led of sensor x
            elif action_type == 68:
                #  68: Press virtual input x
                actions.append(BasicAction(action_type=1, action=0, device_nr=action_number))
            elif action_type == 69:
                #  69: Release virtual input x
                actions.append(BasicAction(action_type=1, action=1, device_nr=action_number))
            #  70: Switch OFF 5V out off all temperature modules (switch ON 5V will automatically happen after 5 minutes)
            #  71: Switch ON 5V out off all temperature modules
            elif action_type == 72:
                #  72: Reset 12V out power on the gateway so all remote modules connected on BUS1 of the Gateway will get a power reset (Master will not respond during 5 seconds)
                actions.append(BasicAction(action_type=253, action=0, device_nr=0))
                actions.append(BasicAction(action_type=253, action=0, device_nr=1))
            #  73: Switch ON DALI group x, see DALI Installation Guide for more details
            #  74: Switch OFF DALI group x, see DALI Installation Guide for more details
            elif action_type == 75:
                #  75: Switch ON CAN power of all CAN controls (micro CAN's will receive power)
                actions.append(BasicAction(action_type=253, action=1, device_nr=1))
            elif action_type == 76:
                #  76: Switch OFF CAN power of all CAN controls (micro CAN's won't receive any power and will be switched off)
                actions.append(BasicAction(action_type=253, action=1, device_nr=0))
            #  79: This Basic Action will set the CleanTimerQueue setting. When Basic actions are added to the timer queue (for delayed action for example), the Master processor will check for the same Basic actions and remove the previous one. When x=0 -> Clean Timer Queue is disabled, when x<>0 -> Clean Timer Queue is enabled (standard setting) - see #Delaying Instructions and see BA235
            #  80 -> 91: Thermostat related
            elif action_type == 100:
                # 100: Roller/Shutter x up (only to be used in Large Installation mode, x<120)
                actions.append(BasicAction(action_type=10, action=1, device_nr=action_number))
            elif action_type == 101:
                # 101: Roller/Shutter x down (only to be used in Large Installation mode, x<120)
                actions.append(BasicAction(action_type=10, action=2, device_nr=action_number))
            elif action_type == 102:
                # 102: Roller/Shutter x stop (only to be used in Large Installation mode, x<120)
                actions.append(BasicAction(action_type=10, action=0, device_nr=action_number))
            elif action_type == 103:
                # 103: Roller/Shutter x up/stop/down/stop... (only to be used in Large Installation mode, x<120)
                actions.append(BasicAction(action_type=10, action=5, device_nr=action_number))
            # 104: All Roller/Shutters of group x up (only to be used in Large Installation mode, x<30)
            # 105: All Roller/Shutters of group x down (only to be used in Large Installation mode, x<30)
            # 106: All Roller/Shutters of group x stop (only to be used in Large Installation mode, x<30)
            # 107: All Roller/Shutters of group x up/stop/down/stop... (only to be used in Large Installation mode, x<30)
            elif action_type == 108:
                # 108: Roller/Shutter x up/stop/up/stop... (only to be used in Large Installation mode, x<120)
                actions.append(BasicAction(action_type=10, action=3, device_nr=action_number))
            elif action_type == 109:
                # 109: Roller/Shutter x down/stop/down/stop... (only to be used in Large Installation mode, x<120)
                actions.append(BasicAction(action_type=10, action=4, device_nr=action_number))
            # 110: All Roller/Shutters of group x up/stop/up/stop... (only to be used in Large Installation mode, x<30)
            # 111: All Roller/Shutters of group x down/stop/down/stop... (only to be used in Large Installation mode, x<30)
            # 112: The Timer of all Roller/Shutters will be disabled (x=0) or enabled (x=1)
            # 113: Enable/disable automatic Roller/Shutter Lock functionality for all Roller/Shutters: When x=0, the roller/shutters will work normally. When x>0, the Roller/shutters will be locked and the normal BA's to stop, up or down a shutter (or group) will be disabled. When a timer was activated to stop a Roller/shutter, even when the automatic Roller/shutter functionality is enabled, will still be executed.
            # 116: Disable input x (0-239)
            # 117: Enable input x (0-239)
            # 118: Reset Pulse Counters of all Modules
            # 120: Put free variable x (0-31) at zero
            # 121: Decrease free variable x (0-31) with 1
            # 122: Increase free variable x (0-31) with 1
            # 123: Decrease free variable x (0-31) with 2
            # 124: Increase free variable x (0-31) with 2
            # 125: Decrease free variable x (0-31) with 3
            # 126: Increase free variable x (0-31) with 3
            # 128 -> 143: Thermostat related
            # 144: Reserved (for Oled)
            # 145 -> 149: Thermostat related
            # 153: Light/Output x on with std timer and overrule/overwrite timer value when light is already switched on
            # 154: Increase light/output level of output/light x with 1 step until programmed Maximum (63) light level is achieved (x<240)
            # 155: Increase light/output level of output/light x with 2 steps until programmed Maximum (63) light level is achieved (x<240)
            # 156: Increase light/output level of output/light x with 3 steps until programmed Maximum (63) light level is achieved (x<240)
            # 157: Dim light/output x down with 1 step until programmed Minimum light level is achieved (x<240)
            # 158: Dim light/output x down with 2 steps until programmed Minimum light level is achieved (x<240)
            # 159: Dim light/output x down with 3 steps until programmed Minimum light level is achieved (x<240)
            elif action_type == 160:
                # 160: Light/Output x Off (x<240)
                actions.append(BasicAction(action_type=0, action=0, device_nr=action_number))
            elif action_type == 161:
                # 161: Light/Output x On (x<240, with standard timer setting, with last dimmer value)
                actions.append(BasicAction(action_type=0, action=1, device_nr=action_number))
            elif action_type == 162:
                # 162: Toggle light/Output x (x<240, with standard timer setting, with last dimmer value), see #Toggling Lights
                actions.append(BasicAction(action_type=0, action=16, device_nr=action_number))
            elif action_type == 163:
                # 163: All lights off (x=any value but <240)
                actions.append(BasicAction(action_type=0, action=255, device_nr=1))
            elif action_type == 164:
                # 164: All outputs including lights off (x=any value but <240)
                actions.append(BasicAction(action_type=0, action=255, device_nr=2))
            elif action_type == 165:
                # 165: Light/Output x On (x<240, with standard timer setting, at minimum dimmer value)
                actions.append(BasicAction(action_type=0, action=2, device_nr=action_number, extra_parameter=1))
            elif action_type == 166:
                # 166: Light/Output x On (x<240, with standard timer setting, at maximum dimmer value)
                actions.append(BasicAction(action_type=0, action=2, device_nr=action_number, extra_parameter=255))
            # 167: Light/Output x On (x<240, with standard timer setting, decrease dimmer value with 5)
            # 168: Light/Output x On (x<240, with standard timer setting, increase dimmer value with 5)
            elif action_type == 169:
                # 169: Set Dimmer value x at minimum (leaving the output at the current state)
                actions.append(BasicAction(action_type=0, action=9, device_nr=action_number, extra_parameter=1))
            elif action_type == 170:
                # 170: Set Dimmer value x at maximum (leaving the output at the current state)
                actions.append(BasicAction(action_type=0, action=9, device_nr=action_number, extra_parameter=255))
            # 171: All lights OFF of a certain floor level or group (x=floor level or group, x=0..254, when x=255 then all lights are selected)
            # 172: All lights ON of a certain floor level or group (x=floor level or group, x=0..254, when x=255 then all lights are selected)
            # 173: Toggle all lights of a certain floor or group (x=floor level or group, x=0..254, when x=255 then all lights are selected), see #Toggling a Floor
            # 174: Toggle Follow function ON (see #Toggling Lights), action number not used but must be < 240
            # 175: Toggle Follow function OFF (see #Toggling Lights), action number not used but must be < 240
            elif 176 <= action_type <= 184:
                # 176: Light/Output x On with dimmer at 10% (x<240, with standard timer setting)
                # 177: Light/Output x On with dimmer at 20% (x<240, with standard timer setting)
                # ...
                # 183: Light/Output x On with dimmer at 80% (x<240, with standard timer setting)
                # 184: Light/Output x On with dimmer at 90% (x<240, with standard timer setting)
                actions.append(BasicAction(action_type=0, action=2, device_nr=action_number,
                                           extra_parameter={176: 25, 177: 51, 178: 76, 179: 102, 180: 127, 181: 153, 182: 178, 183: 204, 184: 229}[action_type]))
            elif 185 <= action_type <= 194:
                # 185: Toggle/Output light x with dimmer at 10% (x<240, with standard timer setting)
                # 186: Toggle light/Output x with dimmer at 20% (x<240, with standard timer setting)
                # ...
                # 193: Toggle light/Output x with dimmer at 90% (x<240, with standard timer setting)
                # 194: Toggle light/Output x with dimmer at 100% (x<240, with standard timer setting)
                actions.append(BasicAction(action_type=0, action=17, device_nr=action_number,
                                           extra_parameter={185: 25, 186: 51, 187: 76, 188: 102, 189: 127, 190: 153, 191: 178, 192: 204, 193: 229, 194: 255}[action_type]))
            elif 195 <= action_type <= 200:
                # 195: Light/Output x on with timer at 2 min 30 and overrule timer value when light is already switched on (x<240, with last dimmer value) - see #Timers
                # 196: Light/Output x on with timer at 7 min 30 and overrule timer value when light is already switched on (x<240, with last dimmer value) - see #Timers
                # 197: Light/Output x on with timer at 15 min and overrule timer value when light is already switched on (x<240, with last dimmer value) - see #Timers
                # 198: Light/Output x on with timer at 25 min and overrule timer value when light is already switched on (x<240, with last dimmer value) - see #Timers
                # 199: Light/Output x on with timer at 37 min and overrule timer value when light is already switched on (x<240, with last dimmer value) - see #Timers
                # 200: Light/Output x on with timer at 52 min and overrule timer value when light is already switched on (x<240, with last dimmer value) - see #Timers
                actions.append(BasicAction(action_type=0, action=4, device_nr=action_number,
                                           extra_parameter={195: 150, 196: 450, 197: 900, 198: 1500, 199: 2220, 200: 3120}[action_type]))
            elif 201 <= action_type <= 206:
                # 201: Light/Output x on with timer at 2 min 30 but doesn't overrule timer value when light is already switched on (x<240, with last dimmer value)
                # 202: Light/Output x on with timer at 7 min 30 but doesn't overrule timer value when light is already switched on (x<240, with last dimmer value)
                # 203: Light/Output x on with timer at 15 min but doesn't overrule timer value when light is already switched on (x<240, with last dimmer value)
                # 204: Light/Output x on with timer at 25 min but doesn't overrule timer value when light is already switched on (x<240, with last dimmer value)
                # 205: Light/Output x on with timer at 37 min but doesn't overrule timer value when light is already switched on (x<240, with last dimmer value)
                # 206: Light/Output x on with timer at 52 min but doesn't overrule timer value when light is already switched on (x<240, with last dimmer value)
                actions.append(BasicAction(action_type=0, action=7, device_nr=action_number,
                                           extra_parameter={201: 150, 202: 450, 203: 900, 204: 1500, 205: 2220, 206: 3120}[action_type]))
            # 207: When current input is pressed for more than 2 seconds, execute group action x (See #Long Press)
            # 208: When current input is pressed for more than 3 seconds, execute group action x (See #Long Press)
            # 209: When current input is pressed for more than 4 seconds, execute group action x (See #Long Press)
            # 210: When current input is pressed for more than 5 seconds, execute group action x (See #Long Press)
            # 211: When current input is pressed for more than 6 seconds, execute group action x (See Note "Long Press")
            # 212: Switch CAN led x OFF (see #Important Remarks)
            # 213: Switch CAN led x ON (see #Important Remarks)
            # 214: Fast blinking of CAN led x (see #Important Remarks)
            # 215: Medium blinking of CAN led x (see #Important Remarks)
            # 216: Slow blinking of CAN led x (see #Important Remarks)
            # 217: Fade ON/OFF of CAN led x (see #Important Remarks)
            elif action_type in [218, 219]:
                # TODO: Tricky one, these are included in a single action on the Core so both parameters
                #       should be set at the same time. Idea: scan the whole sequence for the other one hoping
                #       that they are both set at the same GroupAction/Input
                # 218: Set minimum brightness of all CAN leds at value x (see #Important Remarks)
                # 219: Set maximum brightness of all CAN leds at value x (see #Important Remarks)
                raise ValueError('Cannot convert multi-instructions')
            # 235: Delay all next instructions with x seconds (x>0 and <249), x=255 -> All next instruction will be executed normally (see #Delaying Instructions and see BA79)
            # 236: Execute all next actions at button release (x=0), x=255 -> All next instructions will be executed normally (see #Additional Actions)
            # 237: Set the freely assigned validation bit x to 1 (x=0 to 255)
            # 238: Set the freely assigned validation bit x to 0 (x=0 to 255)
            # 239: Toggle the freely assigned validation bit x (x=0 to 255)
            elif action_type == 240:
                # 240: IF THEN ELSE ENDIF
                if action_number == 0:  # X=0 -> IF
                    actions.append(BasicAction(action_type=100, action=0))
                elif action_number == 1:  # X=1 -> AND
                    actions.append(BasicAction(action_type=100, action=90))
                elif action_number == 2:  # X=2 -> OR
                    actions.append(BasicAction(action_type=100, action=91))
                elif action_number == 10:  # X=10 -> THEN
                    actions.append(BasicAction(action_type=100, action=150))
                elif action_number == 20:  # X=20 -> ELSE
                    actions.append(BasicAction(action_type=100, action=200))
                elif action_number == 255:  # X=255 -> ENDIF
                    actions.append(BasicAction(action_type=100, action=255))
                else:  # X = 3 -> XOR, X=4 -> NAND, X=5 -> NOR, X=6 -> NXOR
                    # TODO: Implement once available
                    raise ValueError('Cannot convert operators: NAND, NOR, NXOR')
            elif action_type == 241:
                # 241: Check if input x is ON (To be used with IF THEN ELSE instruction)
                actions.append(BasicAction(action_type=100, action=12, device_nr=action_number))
            elif action_type == 242:
                # 242: Check if input x is OFF (To be used with IF THEN ELSE instruction)
                actions.append(BasicAction(action_type=100, action=13, device_nr=action_number))
            elif action_type == 243:
                # 243: Check if Light/Output x is ON (To be used with IF THEN ELSE instruction)
                actions.append(BasicAction(action_type=100, action=10, device_nr=action_number))
            elif action_type == 244:
                # 244: Check if Light/Output x is OFF (To be used with IF THEN ELSE instruction)
                actions.append(BasicAction(action_type=100, action=11, device_nr=action_number))
            elif action_type == 245:
                # 245: Check if Validation bit x is ON (To be used with IF THEN ELSE instruction)
                actions.append(BasicAction(action_type=100, action=14, device_nr=action_number))
            elif action_type == 246:
                # 246: Check if Validation bit x is OFF (To be used with IF THEN ELSE instruction)
                actions.append(BasicAction(action_type=100, action=15, device_nr=action_number))
            elif 247 <= action_type <= 250:
                # TODO: Need multi instruction parsing
                # 247: Check if temperature sensor 0-31 (x=0-31) or if humidity sensor 0-31 (x=32-63) or if light sensor 0-31 (x=64-95) or if temperature setpoint 0-23 (x=96-119) or if free variable 0-31 (x=128-159) or if time hour (x=228) or if time minute (x=229) or if day (x=230) is or if thermostat mode (x=235)  (always to be followed by action type 248 or 249 or 250) (see #Additional Input Values). All environmental parameters are written in System Value
                # 248: is equal to x (to be used always with action type 247) (see #Additional Input Values)
                # 249: is higher than x (to be used always with action type 247) (see #Additional Input Values)
                # 250: is lower than x (to be used always with action type 247) (see #Additional Input Values)
                raise ValueError('Cannot convert multi-instructions')
            elif action_type == 254:
                # 254: Reset the Master
                actions.append(BasicAction(action_type=254, action=0))
        return actions
