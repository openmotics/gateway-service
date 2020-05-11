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

from gateway.models import ThermostatGroup, Feature


def migrate(migrator, database, fake=False, **kwargs):
    ThermostatGroup.get_or_create(number=0, name='default', on=True)
    Feature.get_or_create(name='thermostats_gateway', enabled=False)


def rollback(migrator, database, fake=False, **kwargs):
    """Write your rollback migrations here."""
    pass
