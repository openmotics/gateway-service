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

from gateway.dto.base import BaseDTO

if False:  # MYPY
    from typing import Optional, Any
    from gateway.dto.apartment import ApartmentDTO


class UserDTO(BaseDTO):
    def __init__(self, id=None, username=None, first_name='', last_name='', role=None,
                 pin_code=None, apartment=None, language='en', accepted_terms=0,
                 is_active=None, email=None):
        self.id = id  # type: Optional[int]
        self.username = username  # type: str
        # if there is no username, but one can be created from the first and last name, create it as well
        if username is None and (first_name != '' or last_name != ''):
            self.username = '{}.{}'.format(first_name.replace(' ', '.').lower(), last_name.replace(' ', '.').lower())
            self.loaded_fields.append('username')  # Append username to the loaded fields
        self.first_name = first_name  # type: str
        self.last_name = last_name  # type: str
        self.role = role  # type: str
        self.pin_code = pin_code  # type: str
        self.apartment = apartment  # type: Optional[ApartmentDTO]
        self.hashed_password = ''  # type: str
        self.language = language  # type: str
        self.is_active = is_active  # type: bool
        self.accepted_terms = accepted_terms  # type: int
        self.email = email  # type: str

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
        if '_hashed_password' in self._loaded_fields:
            self._loaded_fields.remove('_hashed_password')
        if 'password' in self._loaded_fields:
            self._loaded_fields.remove('password')

    def set_password(self, password):
        # type: (str) -> None
        """
        Sets the hashed password field of the UserDTO object, this way no clear-text passwords are used.
        """
        if password == '':
            raise ValueError("Password cannot be empty")
        self.hashed_password = UserDTO._hash_password(password)

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
                self.is_active == other.is_active and
                self.accepted_terms == other.accepted_terms and
                self.email == other.email)

