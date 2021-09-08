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
"""
eSafe initial migration
"""

from shutil import copyfile
import os
import logging
import uuid

import constants
from gateway.migrations.base_migrator import BaseMigrator
from gateway.models import User, Apartment, Delivery, Config, RFID
from gateway.enums import Languages

logger = logging.getLogger(__name__)

if False:  # MyPy
    from typing import Optional, Dict, Any


class EsafeMigrator(BaseMigrator):

    MIGRATION_KEY = 'esafe_v2'

    # translate the language to the ISO language
    lang_translate = {
        'ned': Languages.NL,
        'eng': Languages.EN,
        'fra': Languages.FR,
        'deu': Languages.DE
    }

    @classmethod
    def _migrate(cls):
        # type: () -> None

        # The old eSafe database will be in the OPENMOTICS_PREFIX path that is set by the eSafe app package
        openmotics_prefix = os.environ.get('OPENMOTICS_PREFIX') or constants.OPENMOTICS_PREFIX  # Make sure to load the latest value of the environ variable
        old_sqlite_db = os.path.join(openmotics_prefix, 'database.db')

        cls.migrate_log("Starting eSafe initial migration for esafe database: {}".format(old_sqlite_db))

        if not os.path.exists(old_sqlite_db):
            cls.migrate_log("Old eSafe database does not exists, skipping migration")
            return

        # Make a copy of the database in case something goes wrong, or the data needs to be accessed for future reference
        gw_database = constants.get_gateway_database_file()
        gw_database_backup = '{}_ESAFE_MIGRATION_BACKUP'.format(gw_database)
        if os.path.exists(gw_database):
            copyfile(gw_database, gw_database_backup)

        import sqlite3
        connection = sqlite3.connect(old_sqlite_db,
                                     detect_types=sqlite3.PARSE_DECLTYPES,
                                     check_same_thread=False,
                                     isolation_level=None)
        cursor = connection.cursor()

        # Migrate Apartments
        # ------------------
        cls.migrate_log("Migrating Apartments")
        apartment_cache = {}  # link of the old ID to the new ORM object
        cls.migrate_log("Deleting existing apartments", level=logging.DEBUG)
        Apartment.delete().where(Apartment.id > 0).execute()

        for row in cursor.execute('SELECT apartment_id, apartment_name, mailbox_rebus_id, doorbell_rebus_id FROM apartment;'):
            apartment_id = row[0]
            apartment_name = row[1]
            mailbox_rebus_id = row[2]
            doorbell_rebus_id = row[3]

            cls.migrate_log("Got apartment: id: {}, name: {}, mailbox: {}, doorbell: {}"
                            .format(apartment_id, apartment_name, mailbox_rebus_id, doorbell_rebus_id),
                            level=logging.DEBUG)

            apartment_orm = Apartment(
                name=apartment_name,
                mailbox_rebus_id=mailbox_rebus_id,
                doorbell_rebus_id=doorbell_rebus_id,
            )
            apartment_orm.save()
            apartment_cache[apartment_id] = apartment_orm

        # Migrate Users
        # ------------------
        cls.migrate_log("Migrating Users")
        user_cache = {}  # link of the old ID to the new ORM object
        for row in cursor.execute('SELECT user_id, user_first_name, user_last_name, user_role, user_code, apartment_id, user_language, is_active FROM user;'):
            user_id = row[0]
            first_name = row[1]
            last_name = row[2]
            role = row[3]
            pin_code = row[4]
            apartment_id = row[5]
            language = row[6] or 'English'
            is_active = row[7]

            cls.migrate_log("Got user: id: {}, first_name: {}, last_name: {}, role: {}, pin_code: {}, apartment_id: {}, language: {}, is_active: {}"
                            .format(user_id,
                                    first_name,
                                    last_name,
                                    role,
                                    pin_code,
                                    apartment_id,
                                    language,
                                    is_active
                                    ),
                            level=logging.DEBUG)

            # double check the apartment_id so that the id did not change with the migration and it can be found again
            if apartment_id is not None:
                apartment_orm_user = apartment_cache.get(apartment_id, None)  # type: Optional[Apartment]
                if apartment_orm_user is None:
                    raise ValueError('Could not find apartment that was linked in the database to the user')
            else:
                apartment_orm_user = None

            language_translated = cls.lang_translate.get(language.lower()[0:3], Languages.EN)

            user_orm = User.get_or_none(pin_code=pin_code)
            if user_orm is None:
                user_orm = User(
                    username=str(uuid.uuid4()),
                    first_name=first_name,
                    last_name=last_name,
                    role=role,
                    pin_code=pin_code,
                    apartment=apartment_orm_user,
                    language=language_translated,
                    is_active=is_active,
                    accepted_terms=1
                )
                user_orm.password = uuid.uuid4().hex
                user_orm.save()
            else:
                cls.migrate_log("User with pin_code '{}' already exists... Skipping the creation of the user.".format(pin_code), level=logging.WARNING)

            user_cache[user_id] = user_orm

        # Migrate RFID
        # ------------------
        cls.migrate_log("Migrating RFID tags")
        for row in cursor.execute('SELECT rfid_id, rfid_tag_string, rfid_uid_manufact, rfid_uid_extension, enter_count, blacklisted, rfid_label, rfid_timestamp_created, rfid_timestamp_last_used, user_id FROM rfid;'):
            rfid_id = row[0]
            rfid_tag_string = row[1]
            rfid_uid_manufact = row[2]
            rfid_uid_extension = row[3]
            enter_count = row[4]
            blacklisted = row[5]
            rfid_label = row[6]
            rfid_timestamp_created = row[7] or '2018-01-01T01:00:00+01:00'
            rfid_timestamp_last_used = row[8]
            user_id = row[9]

            cls.migrate_log("Got rifd: rfid_id: {}, rfid_tag_string: {}, rfid_uid_manufact: {}, rfid_uid_extension: {}, enter_count: {}, blacklisted: {}, rfid_label: {}, rfid_timestamp_created: {}, rfid_timestamp_last_used: {}, user_id: {}"
                            .format(rfid_id,
                                    rfid_tag_string,
                                    rfid_uid_manufact,
                                    rfid_uid_extension,
                                    enter_count,
                                    blacklisted,
                                    rfid_label,
                                    rfid_timestamp_created,
                                    rfid_timestamp_last_used,
                                    user_id
                                    ),
                            level=logging.DEBUG)

            rfid_orm = RFID.get_or_none(uid_manufacturer=rfid_uid_manufact)  # type: RFID
            user_orm = user_cache[user_id]
            if rfid_orm is not None:
                cls.migrate_log("RFID with uuid '{}' already exists... Removing the pin code and adding it back with the eSafe badge to the user with eSafe id: '{}'".format(rfid_uid_manufact, user_id), level=logging.WARNING)
                RFID.delete_by_id(rfid_orm.id)
            rfid_orm = RFID(
                tag_string=rfid_tag_string,
                uid_manufacturer=rfid_uid_manufact,
                uid_extension=rfid_uid_extension,
                enter_count=enter_count,
                blacklisted=blacklisted,
                label=rfid_label,
                timestamp_created=rfid_timestamp_created,
                timestamp_last_used=rfid_timestamp_last_used,
                user=user_orm
            )
            rfid_orm.save()

        # Migrate Deliveries
        # ------------------
        cls.migrate_log("Migrating Deliveries")

        # Delete all the existing deliveries and copy the eSafe V1 deliveries in
        Delivery.delete().where(Delivery.id > 0).execute()

        for row in cursor.execute('SELECT delivery_id, delivery_type, delivery_timestamp_delivery, delivery_timestamp_pickup, delivery_courier_firm, delivery_signature_delivery, delivery_signature_pickup, parcelbox_rebus_id, user_id_pickup, user_id_delivery FROM delivery;'):
            delivery_id = row[0]
            delivery_type = row[1]
            delivery_timestamp_delivery = row[2]
            delivery_timestamp_pickup = row[3]
            delivery_courier_firm = row[4]
            delivery_signature_delivery = row[5]
            delivery_signature_pickup = row[6]
            parcelbox_rebus_id = row[7]
            user_id_pickup = row[8]
            user_id_delivery = row[9]

            cls.migrate_log("Got Delivery: delivery_id: {}, delivery_type: {}, delivery_timestamp_delivery: {}, delivery_timestamp_pickup: {}, delivery_courier_firm: {}, delivery_signature_delivery: {}, delivery_signature_pickup: {}, parcelbox_rebus_id: {}, user_id_pickup: {}, user_id_delivery: {}"
                            .format(delivery_id,
                                    delivery_type,
                                    delivery_timestamp_delivery,
                                    delivery_timestamp_pickup,
                                    delivery_courier_firm,
                                    delivery_signature_delivery,
                                    delivery_signature_pickup,
                                    parcelbox_rebus_id,
                                    user_id_pickup,
                                    user_id_delivery
                                    ),
                            level=logging.DEBUG)

            user_delivery_orm = user_cache.get(user_id_delivery, None)
            user_pickup_orm = user_cache.get(user_id_pickup, None)

            delivery_orm = Delivery(
                type=delivery_type,
                timestamp_delivery=delivery_timestamp_delivery,
                timestamp_pickup=delivery_timestamp_pickup,
                courier_firm=delivery_courier_firm,
                signature_delivery=delivery_signature_delivery,
                signature_pickup=delivery_signature_pickup,
                parcelbox_rebus_id=parcelbox_rebus_id,
                user_delivery=user_delivery_orm,
                user_pickup=user_pickup_orm
            )
            delivery_orm.save()

        # Migrate Config
        # ------------------
        cls.migrate_log("Migrating Config")

        config = {}
        for row in cursor.execute('SELECT key, value FROM system;'):
            key = row[0]
            value = row[1]

            cls.migrate_log("Got config: key: {}, value: {}"
                            .format(key, value),
                            level=logging.DEBUG)

            config[key] = value

        is_bool = [
            'doorbell_enabled',
            'rfid_enabled',
            'rfid_security_enabled',
            'activate_change_first_name_enabled',
            'activate_change_last_name_enabled',
            'activate_change_language_enabled',
            'activate_change_user_code_enabled'
        ]
        is_language = [
            'language'
        ]

        def save_key_into_config(old_key, new_key, existing_config_dict):
            conf_value = config[old_key]
            if old_key in is_bool:
                conf_value = bool(conf_value)
            if old_key in is_language:
                conf_value = cls.lang_translate.get(conf_value.lower()[0:3], Languages.EN)
            existing_config_dict[new_key] = conf_value
            return existing_config_dict

        # manually group the correct settings in one dict per namespace:
        # 1. Doorbell
        doorbell_config = {}  # type: Dict[str, Any]
        for old_key, new_key in {'doorbell_enabled': 'enabled'}.items():
            doorbell_config = save_key_into_config(old_key, new_key, doorbell_config)

        cls.migrate_log("Doorbell_config: {}".format(doorbell_config), level=logging.DEBUG)

        # 2. RFID
        rfid_config = {}  # type: Dict[str, Any]
        for old_key, new_key in {'rfid_enabled': 'enabled', 'max_rfid': 'max_tags', 'rfid_security_enabled': 'security_enabled'}.items():
            rfid_config = save_key_into_config(old_key, new_key, rfid_config)
        cls.migrate_log("rfid config: {}".format(rfid_config), level=logging.DEBUG)

        # 3. RFID Sector
        rfid_sector_config = {}  # type: Dict[str, Any]
        for old_key, new_key in {'rfid_sector_block': 'rfid_sector_block'}.items():
            rfid_sector_config = save_key_into_config(old_key, new_key, rfid_sector_config)
        cls.migrate_log("rfid sector config: {}".format(rfid_sector_config), level=logging.DEBUG)

        # 4. global
        global_config = {}  # type: Dict[str, Any]
        for old_key, new_key in {'device_name': 'device_name',
                                 'country': 'country',
                                 'postal_code': 'postal_code',
                                 'city': 'city',
                                 'street': 'street',
                                 'house_number': 'house_number',
                                 'language': 'language'}.items():
            global_config = save_key_into_config(old_key, new_key, global_config)
        cls.migrate_log("global config: {}".format(global_config), level=logging.DEBUG)

        # 5. Activate User Config
        activate_user_config = {}  # type: Dict[str, Any]
        for new_key, old_key in {'change_first_name': 'activate_change_first_name_enabled',
                                 'change_last_name': 'activate_change_last_name_enabled',
                                 'change_language': 'activate_change_language_enabled',
                                 'change_pin_code': 'activate_change_user_code_enabled'}.items():
            activate_user_config = save_key_into_config(old_key, new_key, activate_user_config)
        cls.migrate_log("activate user config: {}".format(activate_user_config), level=logging.DEBUG)

        Config.set_entry('doorbell_config', doorbell_config)
        Config.set_entry('rfid_config', rfid_config)
        Config.set_entry('rfid_sector_block_config', rfid_sector_config)
        Config.set_entry('global_config', global_config)
        Config.set_entry('activate_user_config', activate_user_config)
        Config.set_entry('rfid_auth_key_A', config['rfid_auth_key_A'])
        Config.set_entry('rfid_auth_key_B', config['rfid_auth_key_B'])

        # When the migration is successful, save the old database under a backup name
        backup_database_name = '{}_ESAFE_BACKUP'.format(old_sqlite_db)
        os.rename(old_sqlite_db, backup_database_name)

