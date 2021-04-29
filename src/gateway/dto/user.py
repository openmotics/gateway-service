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
User DTO
"""

import hashlib

from gateway.dto.base import BaseDTO, capture_fields

if False:  # MYPY
    from typing import Optional, Any
    from gateway.dto.apartment import ApartmentDTO


class UserDTO(BaseDTO):
    @capture_fields
    def __init__(self, id=None, username=None, first_name='', last_name='', role=None,
                 pin_code=None, apartment=None, accepted_terms=0):
        self.id = id  # type: Optional[int]
        self.username = username  # type: str
        # if there is no username, but one can be created from the first and last name, create it as well
        if username is None and (first_name != '' or last_name != ''):
            self.username = '{}.{}'.format(first_name.replace(' ', '.').lower(), last_name.replace(' ', '.').lower())  # type: str
            self.loaded_fields.append('username')  # Append username to the loaded fields
        self.first_name = first_name  # type: str
        self.last_name = last_name  # type: str
        self.role = role  # type: str
        self.pin_code = pin_code  # type: str
        self.apartment = apartment  # type: ApartmentDTO
        self.hashed_password = ''  # type: str
        self.accepted_terms = accepted_terms  # type: int
        # if no first and last name is given, allow to set to set the name to username
        if first_name == '' and last_name == '':
            self.username = username

    @staticmethod
    def _hash_password(password):
        # type: (str) -> str
        """
        Hash the password using sha1.
        """
        sha = hashlib.sha1()
        sha.update(b'OpenMotics')
        sha.update(password.encode('utf-8'))
        return sha.hexdigest()

    def clear_password(self):
        # Type: () -> None
        """
        Clears the hashed password field so that it is hidden for future reference.
        """
        self.hashed_password = ''

    def set_password(self, password):
        # type: (str) -> None
        """
        Sets the hashed password field of the UserDTO object, this way no clear-text passwords are used.
        """
        if password == '':
            raise ValueError("Password cannot be empty")

        self.hashed_password = UserDTO._hash_password(password)
        self.loaded_fields.append('hashed_password')

    def __eq__(self, other):
        # type: (Any) -> bool
        if not isinstance(other, UserDTO):
            return False
        return (self.id == other.id and
                self.username == other.username and
                self.first_name == other.first_name and
                self.last_name == other.last_name and
                self.role == other.role and
                self.pin_code == other.pin_code and
                self.apartment == other.apartment and
                self.accepted_terms == other.accepted_terms)

