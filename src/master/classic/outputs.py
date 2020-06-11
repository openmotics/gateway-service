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

    def partial_update(self, on_outputs):  # type: (list) -> None
        """
        Update the status of the outputs using a list of tuples containing the
        light id an the dimmer value of the lights that are on.
        """
        on_dict = {}
        for on_output in on_outputs:
            on_dict[on_output[0]] = on_output[1]

        with self._merge_lock:
            for output_id, output in six.iteritems(self._outputs):
                self._update(output_id, {'status': output_id in on_dict,
                                         'dimmer': on_dict.get(output_id)})

    def full_update(self, outputs):
        """ Update the status of the outputs using a list of Outputs. """
        obsolete_ids = list(self._outputs.keys())
        for output in outputs:
            output_id = output['id']
            if output_id in obsolete_ids:
                obsolete_ids.remove(output_id)
            changed = self._create_or_update(output_id, output)
            if changed:
                self._report_change(output_id)
        for output_id in obsolete_ids:
            self._delete(output_id)

    def get_outputs(self):
        """ Return the list of Outputs. """
        return list(self._outputs.values())

    def get_output(self, output_id):
        """ Return the list of Outputs. """
        return self._outputs.get(output_id)

    def update_locked(self, output_id, locked):  # type: (int, bool) -> None
        """ Updated the locked atttribute of the Output. """
        changed = self._set_locked(output_id, locked)
        if changed:
            self._report_change(output_id)

    def _create(self, output_id, output):  # type: (int, dict) -> None
        if self._outputs.get(output_id):
            raise KeyError('Output {} already exists')
        with self._merge_lock:
            self._outputs[output_id] = {'status': output['status'],
                                        'dimmer': output['dimmer'],
                                        'locked': output.get('locked', False)}

    def _update(self, output_id, output):  # type: (int, dict) -> bool
        changed = False
        if not self._outputs.get(output_id):
            raise KeyError('Output {} does not exist'.format(output_id))
        else:
            changed |= self._set_status(output_id, output['status'])
            changed |= self._set_dimmer(output_id, output['dimmer'])
            if output.get('locked'):
                changed |= self._set_locked(output_id, output['locked'])
        return changed

    def _delete(self, output_id):  # type: (int) -> None
        if not self._outputs.get(output_id):
            raise KeyError('Output {} does not exist'.format(output_id))
        with self._merge_lock:
            del self._outputs[output_id]

    def _create_or_update(self, output_id, output):  # type: (int, dict) -> bool
        changed = False
        if self._outputs.get(output_id):
            changed |= self._update(output_id, output)
        else:
            self._create(output_id, output)
            changed = True
        return changed

    def _set_status(self, output_id, status):  # type: (int, bool) -> bool
        """ Sets the status on an output """
        changed = False
        output = self._outputs.get(output_id)
        if not output:
            logger.warning('cannot set output {} to state {}, unknown output'.format(output_id, status))
        elif output.get('status') != status:
            with self._merge_lock:
                output['status'] = status
            changed = True
        return changed

    def _set_dimmer(self, output_id, dimmer):  # type: (int, int) -> bool
        """ Sets the dimmer value on an output """
        changed = False
        output = self._outputs.get(output_id)
        if not output:
            logger.warning('cannot set output {} to dimmer value {}, unknown output'.format(output_id, dimmer))
        elif output.get('dimmer') != dimmer:
            with self._merge_lock:
                output['dimmer'] = dimmer
            changed = True
        return changed

    def _set_locked(self, output_id, locked):  # type: (int, bool) -> bool
        """ Sets the locked status on an output """
        changed = False
        output = self._outputs.get(output_id)
        if not output:
            logger.warning('cannot set output {} to locked state {}, unknown output'.format(output_id, locked))
        elif output.get('locked') != locked:
            with self._merge_lock:
                output['locked'] = locked
            changed = True
        return changed

    def _report_change(self, output_id):
        if self._on_output_change is not None:
            output = self._outputs[output_id]
            self._on_output_change(output_id, {'on': bool(output['status']),
                                               'value': int(output['dimmer']),
                                               'locked': bool(output.get('locked', False))})
