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

from gateway.models import (
    ThermostatGroup, Feature, Output, ValveToThermostat, OutputToThermostatGroup,
    DaySchedule, Preset, Thermostat, Valve, PumpToValve, Pump
)


def migrate(migrator, database, fake=False, **kwargs):
    database.create_tables([Output, ThermostatGroup, OutputToThermostatGroup, Thermostat, Valve,
                            ValveToThermostat, Output, Preset, DaySchedule, Pump, PumpToValve, Feature])


def rollback(migrator, database, fake=False, **kwargs):
    """Write your rollback migrations here."""
    pass
