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

import logging
from ioc import INJECTED, Inject
from gateway.migrations.base_migrator import BaseMigrator
from gateway.models import Input
from platform_utils import Platform

if False:  # MYPY
    from typing import Dict, List, Any
    from gateway.hal.master_controller_classic import MasterClassicController
    from master.classic.eeprom_extension import EepromExtension

logger = logging.getLogger('openmotics')


class InputMigrator(BaseMigrator):

    MIGRATION_KEY = 'input_event_enabled'

    @classmethod
    @Inject
    def _migrate(cls, master_controller=INJECTED):  # type: (MasterClassicController) -> None
        # Core(+) platforms never had non-ORM rooms
        if Platform.get_platform() != Platform.Type.CLASSIC:
            return

        # Import legacy code
        @Inject
        def _load_eeprom_extension(eeprom_extension=INJECTED):
            # type: (EepromExtension) -> EepromExtension
            return eeprom_extension

        eext_controller = _load_eeprom_extension()
        from master.classic.eeprom_models import InputConfiguration

        # Main objects
        eeprom_model = InputConfiguration
        try:
            for classic_orm in master_controller._eeprom_controller.read_all(eeprom_model):
                try:
                    object_id = classic_orm.id
                    if object_id is None:
                        continue
                    if classic_orm.module_type not in ['i', 'I']:
                        InputMigrator._delete_eext_fields(eext_controller, eeprom_model.__name__, object_id, ['event_enabled'])
                        continue
                    event_enabled = InputMigrator._read_eext_fields(eext_controller,
                                                                    eeprom_model.__name__,
                                                                    object_id,
                                                                    ['event_enabled']).get('event_enabled', 'False') == 'True'
                    object_orm, _ = Input.get_or_create(number=object_id)  # type: ignore
                    object_orm.event_enabled = event_enabled
                    object_orm.save()
                    InputMigrator._delete_eext_fields(eext_controller, eeprom_model.__name__, object_id, ['event_enabled'])
                except Exception:
                    logger.exception('Could not migrate single {0}'.format(eeprom_model.__name__))
        except Exception:
            logger.exception('Could not migrate {0}s'.format(eeprom_model.__name__))

    @staticmethod
    def _read_eext_fields(eext_controller, model_name, model_id, fields):
        # type: (EepromExtension, str, int, List[str]) -> Dict[str, Any]
        data = {}
        for field in fields:
            value = eext_controller.read_data(model_name, model_id, field)
            if value is not None:
                data[field] = value
        return data

    @staticmethod
    def _delete_eext_fields(eext_controller, model_name, model_id, fields):
        # type: (EepromExtension, str, int, List[str]) -> None
        for field in fields:
            eext_controller.delete_data(model_name, model_id, field)
