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
The outputs module contains classes to track the current state of the outputs on
the master.
"""

from __future__ import absolute_import
from threading import Lock
import six
import logging

if False:  # MYPY
    from typing import Any, Dict, List, Tuple

logger = logging.getLogger("openmotics")


class OutputStatus(object):
    """ Contains a cached version of the current output of the controller. """

    def __init__(self, on_output_change=None):
        """
        Create a status object using a list of outputs (can be None),
        and a refresh period: the refresh has to be invoked explicitly.
        """
        self._outputs = {}
        self._on_output_change = on_output_change
        self._merge_lock = Lock()

    def partial_update(self, on_outputs):  # type: (List[Tuple[int, int]]) -> None
        """
        Update the status of the outputs using a list of tuples containing the
        light id an the dimmer value of the lights that are on.
        """
        on_dict = {on_output[0]: {'status': True,
                                  'dimmer': on_output[1]}
                   for on_output in on_outputs}

        for output_id in self._outputs:
            if output_id in on_dict:
                changed = self._update(output_id, on_dict[output_id])
            else:
                changed = self._update(output_id, {'status': False})
            if changed:
                self._report_change(output_id)

    def full_update(self, outputs):
        """ Update the status of the outputs using a list of Outputs. """
        obsolete_ids = list(self._outputs.keys())
        for output in outputs:
            output_id = output['id']
            if output_id in obsolete_ids:
                obsolete_ids.remove(output_id)
            if self._update(output_id, output):
                self._report_change(output_id)
        for output_id in obsolete_ids:
            self._outputs.pop(output_id, None)

    def get_outputs(self):
        """ Return the list of Outputs. """
        return list(self._outputs.values())

    def get_output(self, output_id):
        """ Return the list of Outputs. """
        return self._outputs.get(output_id)

    def update_locked(self, output_id, locked):  # type: (int, bool) -> None
        """ Updated the locked atttribute of the Output. """
        if self._update(output_id, {'locked': locked}):
            self._report_change(output_id)

    def _update(self, output_id, new_output_data):  # type: (int, Dict[str, Any]) -> bool
        changed = False
        with self._merge_lock:
            if output_id not in self._outputs:
                self._outputs[output_id] = {'id': output_id,
                                            'ctimer': int(new_output_data.get('ctimer', 0)),
                                            'status': bool(new_output_data.get('status', False)),
                                            'dimmer': int(new_output_data.get('dimmer', 0)),
                                            'locked': bool(new_output_data.get('locked', False))}
                changed = True
            else:
                output = self._outputs[output_id]
                if 'ctimer' in new_output_data:
                    output['ctimer'] = int(new_output_data['ctimer'])
                if 'status' in new_output_data:
                    status = bool(new_output_data['status'])
                    changed |= output.get('status') != status
                    output['status'] = status
                if 'dimmer' in new_output_data:
                    dimmer = int(new_output_data['dimmer'])
                    changed |= output.get('dimmer') != dimmer
                    output['dimmer'] = dimmer
                if 'locked' in new_output_data:
                    locked = bool(new_output_data['locked'])
                    changed |= output.get('locked') != locked
                    output['locked'] = locked
        return changed

    def _report_change(self, output_id):
        if self._on_output_change is not None:
            output = self._outputs[output_id]
            self._on_output_change(output_id, {'on': output['status'],
                                               'value': output['dimmer'],
                                               'locked': output['locked']})
