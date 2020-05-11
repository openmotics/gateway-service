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

from gateway.models import Room, Floor, Shutter, ShutterGroup, Sensor, PulseCounter, Input


def migrate(migrator, database, fake=False, **kwargs):
    database.create_tables([Room, Floor, Shutter, ShutterGroup,
                            Sensor, PulseCounter, Input])  # This will - for some reason - add the foreigns keys as well


def rollback(migrator, database, fake=False, **kwargs):
    """Write your rollback migrations here."""
    pass
