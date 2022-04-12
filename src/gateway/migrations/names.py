# Copyright (C) 2022 OpenMotics BV
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

from gateway.migrations.base_migrator import BaseMigrator
from gateway.models import Database, Output, Input, Shutter, GroupAction
from ioc import INJECTED, Inject

if False:  # MYPY
    from gateway.hal.master_controller import MasterController

logger = logging.getLogger(__name__)


class NamesMigrator(BaseMigrator):

    MIGRATION_KEY = 'names'

    @classmethod
    @Inject
    def _migrate(cls, master_controller=INJECTED):  # type: (MasterController) -> None
        with Database.get_session() as db:
            for model_cls, name in [(Output, 'outputs'),
                                    (Input, 'inputs'),
                                    (Shutter, 'shutters'),
                                    (GroupAction, 'group_actions')]:
                for dto in getattr(master_controller, 'load_{0}'.format(name))():
                    orm_object = db.query(model_cls).filter(model_cls.number == dto.id).one_or_none()  # type: ignore
                    if orm_object is not None and orm_object.name == '':
                        orm_object.name = dto.name
            db.commit()
