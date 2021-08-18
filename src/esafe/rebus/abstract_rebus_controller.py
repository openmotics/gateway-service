# Copyright (C) 2021 OpenMotics BV
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
Rebus controller interface
"""


class RebusControllerInterface(object):

    ######################
    # Controller Functions
    ######################

    def start(self):
        raise NotImplementedError()

    def stop(self):
        raise NotImplementedError()

    # Mailbox Functions

    def get_mailboxes(self, rebus_id=None):
        raise NotImplementedError()

    # ParcelBox Functions

    def get_parcelboxes(self, rebus_id=None, size=None, available=False):
        raise NotImplementedError()

    # Generic Functions (parcelbox and mailbox)

    def open_box(self, rebus_id):
        raise NotImplementedError()

    # Doorbells

    def get_doorbells(self):
        raise NotImplementedError()

    def ring_doorbell(self, doorbell_id):
        raise NotImplementedError()

    ######################
    # REBUS COMMANDS
    ######################

    def get_lock_status(self, lock_id):
        raise NotImplementedError()

    def toggle_rebus_power(self, duration=0.5):
        raise NotImplementedError()

    ########################
    # VERIFICATION COMMANDS
    ########################

    def verify_device_exists(self, device_id):
        raise NotImplementedError()
