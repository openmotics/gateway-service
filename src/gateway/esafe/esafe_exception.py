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


class EsafeError(Exception):
    DESC = 'General Esafe Error'

    @property
    def message(self):
        return self.__class__.DESC


class EsafeItemDoesNotExistError(EsafeError):
    DESC = 'Item does not exist'


class EsafeStateError(EsafeError):
    DESC = 'State error'


class EsafeWrongInputParametersError(EsafeError):
    DESC = 'Wrong input parameter'


class EsafeParseError(EsafeError):
    DESC = 'Could not parse input'


class EsafeTimeOutError(EsafeError):
    DESC = 'Timeout Exception'


class EsafeInvalidOperationError(EsafeError):
    DESC = 'Invalid Operation'


class EsafeUnAuthorizedError(EsafeError):
    DESC = 'Unauthorized operation'


class EsafeNotImplementedError(EsafeError):
    DESC = 'Not implemented'


class EsafeForbiddenError(EsafeError):
    DESC = 'Action forbidden'
