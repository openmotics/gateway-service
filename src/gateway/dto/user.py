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


class UserDTO(BaseDTO):

    @staticmethod
    def _hash_password(password):
        # type: (str) -> str
        """ 
        Hash the password using sha1. 
        """
        sha = hashlib.sha1()
        sha.update('OpenMotics')  # type: ignore
        sha.update(password)  # type: ignore
        return sha.hexdigest()

    def __init__(self, username, accepted_terms=0):
        # type: (str, int) -> None
        self.username = username
        self.hashed_password= ''
        self.accepted_terms = accepted_terms
    
    def clear_password(self):
        # Type: () -> None
        """
        Clears the hashed password field so that it is hidden for future reference.
        """
        self.hashed_password = ''

    def set_password(self, password):
        # type: (str) -> None
        """
        Sets the hashed password field of the UserDTO object, this way no cleartext passwords are used.
        """
        if password == '':
            raise ValueError("Password cannot be empty")

        self.hashed_password = UserDTO._hash_password(password)

    def __str__(self):
        return "UserDTO: {}".format(vars(self))

    def __eq__(self, other):
        if not isinstance(other, UserDTO):
            return False
        return self.username.lower() == other.username.lower()

