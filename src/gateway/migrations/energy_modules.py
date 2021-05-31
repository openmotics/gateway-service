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

import os
import logging
import constants
from ioc import INJECTED, Inject
from gateway.migrations.base_migrator import BaseMigrator
from gateway.models import EnergyModule, EnergyCT, Module
from gateway.dto import ModuleDTO

if False:  # MYPY
    from gateway.hal.master_controller_classic import MasterClassicController

logger = logging.getLogger(__name__)


class EnergyModulesMigrator(BaseMigrator):

    MIGRATION_KEY = 'energy_modules'
    NUM_CTS = {8: 8, 12: 12, 1: 8}

    @classmethod
    @Inject
    def _migrate(cls, master_controller=INJECTED):  # type: (MasterClassicController) -> None
        old_sqlite_db = constants.get_power_database_file()
        if os.path.exists(old_sqlite_db):
            try:
                import sqlite3
                connection = sqlite3.connect(old_sqlite_db,
                                             detect_types=sqlite3.PARSE_DECLTYPES,
                                             check_same_thread=False,
                                             isolation_level=None)
                select_fields = ['id', 'name', 'address', 'version']
                for i in range(12):
                    select_fields += ['input{0}'.format(i), 'sensor{0}'.format(i), 'times{0}'.format(i), 'inverted{0}'.format(i)]
                cursor = connection.cursor()
                for row in cursor.execute('SELECT {0} FROM power_modules ORDER BY id ASC;'.format(', '.join(select_fields))):
                    try:
                        row_data = dict(zip(select_fields, row))
                        address = str(row_data['address'])
                        module = Module.get_or_none(source=ModuleDTO.Source.GATEWAY,
                                                    address=address)
                        if module is None:
                            module = Module(source=ModuleDTO.Source.GATEWAY,
                                            address=address,
                                            hardware_type=ModuleDTO.HardwareType.PHYSICAL)
                        else:
                            module.hardware_type = ModuleDTO.HardwareType.PHYSICAL
                        module.save()

                        module_id = int(row_data['id'])
                        version = int(row_data['version'])
                        energy_module = EnergyModule.get_or_none(number=module_id)
                        if energy_module is None:
                            energy_module = EnergyModule(number=module_id,
                                                         version=version,
                                                         name=row_data['name'])
                        else:
                            energy_module.version = version
                            energy_module.name = row_data['name']
                        energy_module.module = module
                        energy_module.save()

                        for i in range(EnergyModulesMigrator.NUM_CTS[version]):
                            ct = EnergyCT.get_or_none(energy_module=energy_module,
                                                      number=i)
                            if ct is None:
                                ct = EnergyCT(energy_module=energy_module,
                                              number=i,
                                              name=row_data['input{0}'.format(i)],
                                              sensor_type=int(row_data['sensor{0}'.format(i)]),
                                              times=row_data['times{0}'.format(i)],
                                              inverted=row_data['inverted{0}'.format(i)] == 1)
                            else:
                                ct.name = row_data['input{0}'.format(i)]
                                ct.sensor_type = int(row_data['sensor{0}'.format(i)])
                                ct.times = row_data['times{0}'.format(i)]
                                ct.inverted = row_data['inverted{0}'.format(i)] == 1
                            ct.save()
                    except Exception:
                        logger.exception('Could not migratie Energy Module')
                os.rename(old_sqlite_db, '{0}.bak'.format(old_sqlite_db))
            except Exception:
                logger.exception('Could not migrate gateway Energy Modules')
