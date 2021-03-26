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


class GatewayException(Exception):
    DESC = 'General Gateway Exception'
    def __init__(self, msg=None, *args):
        self.extra_message = msg

    @property
    def message(self):
        result = self.__class__.DESC
        if self.extra_message is not None:
            result += ': {}'.format(self.extra_message)
        return result


class UnsupportedException(GatewayException):
    DESC = 'action is not supported'


class ServiceUnavailableException(GatewayException):
    DESC = 'Service is unavailable'


class TermsNotAcceptedException(GatewayException):
    DESC = 'Terms are not accepted'


class ItemDoesNotExistException(GatewayException):
    DESC = 'Item does not exist'


class StateException(GatewayException):
    DESC = 'State Exception'


class WrongInputParametersException(GatewayException):
    DESC = 'Wrong input parameter'


class ParseException(GatewayException):
    DESC = 'Could not parse input'


class TimeOutException(GatewayException):
    DESC = 'Timeout Exception'


class InvalidOperationException(GatewayException):
    DESC = 'Invalid Operation'


class UnAuthorizedException(GatewayException):
    DESC = 'Unauthorized operation'


class NotImplementedException(GatewayException):
    DESC = 'Not implemented'


class ForbiddenException(GatewayException):
    DESC = 'Action forbidden'
