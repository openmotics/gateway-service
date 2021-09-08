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
Test of the eSafe migrations
"""

from __future__ import absolute_import

import unittest
import os

from peewee import SqliteDatabase

from gateway.dto import UserDTO, ApartmentDTO, DeliveryDTO, RfidDTO
from gateway.mappers import UserMapper, ApartmentMapper, DeliveryMapper, RfidMapper
from gateway.models import Apartment, User, Delivery, Config, RFID, DataMigration
from gateway.migrations import EsafeMigrator
from gateway.pubsub import PubSub
from gateway.rfid_controller import RfidController
from gateway.system_config_controller import SystemConfigController
from ioc import SetTestMode, SetUpTestInjections

import logging
from logs import Logs


logger = logging.getLogger(__name__)

MODELS = [Apartment, User, Delivery, Config, RFID, DataMigration]


class EsafeMigrationTest(unittest.TestCase):
    """ Tests for eSafe migration. """

    def log(self, message='', level=logging.INFO):
        message = "[EsafeMigratorTest] {}".format(message)
        logger.log(level=level, msg=message)

    @classmethod
    def setUpClass(cls):
        super(EsafeMigrationTest, cls).setUpClass()
        SetTestMode()
        cls.pubsub = PubSub()
        SetUpTestInjections(pubsub=cls.pubsub)
        cls.system_config_controller = SystemConfigController()
        cls.rfid_controller = RfidController(system_config_controller=cls.system_config_controller)
        Logs.setup_logger(log_level_override=logging.NOTSET)

    @classmethod
    def tearDownClass(cls):
        super(EsafeMigrationTest, cls).tearDownClass()

    def setUp(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.esafe_db_location = os.path.join(current_dir, 'database.db')

        # Set the environment variable so the migration script knows where to look for the esafe database
        os.environ['OPENMOTICS_PREFIX'] = current_dir

        print(os.environ['OPENMOTICS_PREFIX'])

        self.test_gw_db = SqliteDatabase(':memory:')
        self.test_esafe_db = SqliteDatabase(self.esafe_db_location)

        self.test_gw_db.bind(MODELS, bind_refs=False, bind_backrefs=False)
        self.test_gw_db.connect()
        self.test_gw_db.create_tables(MODELS)
        self.gw_cursor = self.test_gw_db.cursor()

        self.test_esafe_db.connect()
        self.esafe_cursor = self.test_esafe_db.cursor()

    def tearDown(self):
        # Delete all the remaining database files that where created during the test migration
        for filename in [self.esafe_db_location, '{}_ESAFE_BACKUP'.format(self.esafe_db_location)]:
            if os.path.exists(filename):
                os.remove(filename)

    def _create_esafe_database_dummy_data(self):
        # This is a literal copy from an existing test eSafe database
        self.log("* Creating fake eSafe data")

        # Users
        # --------------
        self.log("* USERS")
        self.esafe_cursor.executescript("""
        PRAGMA foreign_keys=OFF;
        BEGIN TRANSACTION;
        CREATE TABLE IF NOT EXISTS "user" (
            `user_id`	INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
            `user_first_name`	TEXT,
            `user_last_name`	TEXT,
            `user_role`	TEXT NOT NULL,
            `user_code`	TEXT NOT NULL UNIQUE,
            `apartment_id`	INTEGER,
            `user_language`	TEXT,
            'is_active' BOOLEAN NOT NULL DEFAULT 1,
            FOREIGN KEY (apartment_id) REFERENCES apartment(apartment_id)
                ON DELETE SET NULL
        );
        INSERT INTO user VALUES(1,NULL,NULL,'TECHNICIAN','1111',NULL,NULL,1);
        INSERT INTO user VALUES(2,NULL,NULL,'ADMIN','0000',NULL,NULL,1);
        INSERT INTO user VALUES(3,'Tesla','Nikola','USER','2222',5,'English',1);
        INSERT INTO user VALUES(7,'pj','t','USER','5555',1,'Nederlands',1);
        INSERT INTO user VALUES(40,'Thomas','Edison','USER','6666',1,'Deutsch',0);
        COMMIT;
        """)

        # Apartments
        # --------------
        self.log("* APARTMENTS")
        self.esafe_cursor.executescript("""
        PRAGMA foreign_keys=OFF;
        BEGIN TRANSACTION;
        CREATE TABLE IF NOT EXISTS "apartment" (
            `apartment_id`	INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
            `apartment_name`	TEXT NOT NULL,
            `mailbox_rebus_id`	INTEGER UNIQUE,
            `doorbell_rebus_id`	INTEGER UNIQUE
        );
        INSERT INTO apartment VALUES(1,'OM 1',32,17);
        INSERT INTO apartment VALUES(5,'app 2',48,18);
        COMMIT;
        """)

        # Config
        # --------------
        self.log("* CONFIG")
        self.esafe_cursor.executescript("""
        PRAGMA foreign_keys=OFF;
        BEGIN TRANSACTION;
        CREATE TABLE IF NOT EXISTS "system" (
            `key` TEXT NOT NULL PRIMARY KEY UNIQUE,
            `value`
        );
        INSERT INTO system VALUES('db_version',6);
        INSERT INTO system VALUES('doorbell_enabled',1);
        INSERT INTO system VALUES('rfid_enabled',1);
        INSERT INTO system VALUES('device_name','ESAFE[]');
        INSERT INTO system VALUES('country','BE');
        INSERT INTO system VALUES('postal_code','');
        INSERT INTO system VALUES('city','');
        INSERT INTO system VALUES('street','vgs');
        INSERT INTO system VALUES('house_number','52');
        INSERT INTO system VALUES('max_rfid',4);
        INSERT INTO system VALUES('rfid_auth_key_A','01deadbeef01');
        INSERT INTO system VALUES('rfid_auth_key_B','01cafebabe01');
        INSERT INTO system VALUES('rfid_sector_block',1);
        INSERT INTO system VALUES('language','English');
        INSERT INTO system VALUES('rfid_security_enabled',0);
        INSERT INTO system VALUES('activate_change_first_name_enabled',1);
        INSERT INTO system VALUES('activate_change_last_name_enabled',1);
        INSERT INTO system VALUES('activate_change_language_enabled',1);
        INSERT INTO system VALUES('activate_change_user_code_enabled',0);
        COMMIT;
        """)

        # RFID
        # --------------
        self.log("* RFID")
        # INSERT INTO rfid VALUES(39,'RFIDTAG1','RFIDTAG1','',-1,0,'test-tag-1','2021-01-29T15:09:49+01:00','2021-01-29T15:10:00+01:00',7);
        self.esafe_cursor.executescript("""
        PRAGMA foreign_keys=OFF;
        BEGIN TRANSACTION;
        CREATE TABLE rfid (
          `rfid_id` INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
          `rfid_tag_string` TEXT NOT NULL UNIQUE,
          `rfid_uid_manufact` TEXT NOT NULL UNIQUE,
          `rfid_uid_extension` TEXT,
          `enter_count` INTEGER NOT NULL,
          `blacklisted` INTEGER NOT NULL,
          `rfid_label` TEXT,
          `rfid_timestamp_created` TEXT,
          `rfid_timestamp_last_used` TEXT,
          `user_id` INTEGER NOT NULL,
          FOREIGN KEY (user_id) REFERENCES user(user_id)
            ON DELETE CASCADE
        );
        INSERT INTO rfid VALUES(39,'RFIDTAG1','RFIDTAG1','',-1,0,'test-tag-1','','2021-01-29T15:10:00+01:00',7);
        INSERT INTO rfid VALUES(41,'RFIDTAG2','RFIDTAG2','',-1,0,'test-tag-2','2021-02-03T14:39:25+01:00','',3);
        INSERT INTO rfid VALUES(44,'RFIDTAG3','RFIDTAG3','RFIDEXT',10,1,'test-tag-3','2021-02-03T14:40:00+02:00','2021-01-29T15:11:00+01:00',40);
        COMMIT;
        """)

        # Delivery
        # --------------
        self.log("* DELIVERY")
        self.esafe_cursor.executescript("""
        PRAGMA foreign_keys=OFF;
        BEGIN TRANSACTION;
        CREATE TABLE IF NOT EXISTS "delivery" (
            `delivery_id`	INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
            `delivery_type`	TEXT NOT NULL,
            `delivery_timestamp_delivery`	TEXT NOT NULL,
            `delivery_timestamp_pickup`	TEXT,
            `delivery_courier_firm`	TEXT,
            `delivery_signature_delivery`	TEXT NOT NULL,
            `delivery_signature_pickup`	TEXT,
            `parcelbox_rebus_id`	INTEGER NOT NULL, /* not unique because picked up deliveries can stay in database*/
            `user_id_pickup`	INTEGER NOT NULL,
            `user_id_delivery`	INTEGER
        );
        INSERT INTO delivery VALUES(1,'DELIVERY','2020-10-07T15:15:24+02:00','2020-10-07T15:19:14+02:00','DPD','Signature_Delivery','Signature_pickup',128,7,NULL);
        INSERT INTO delivery VALUES(2,'DELIVERY','2020-10-07T15:16:49+02:00','2021-01-07T16:54:55+01:00','UPS','','',80,3,NULL);
        INSERT INTO delivery VALUES(3,'RETURN','2020-10-07T15:28:19+02:00','2020-10-07T15:28:42+02:00',NULL,'','',128,30,5);
        INSERT INTO delivery VALUES(4,'DELIVERY','2020-11-24T16:39:15+01:00',NULL,NULL,'','',128,7,NULL);
        INSERT INTO delivery VALUES(5,'DELIVERY','2020-12-06T12:49:50+01:00','2021-01-05T09:51:41+01:00','Bpost','','',64,7,NULL);
        INSERT INTO delivery VALUES(6,'DELIVERY','2021-01-05T09:57:47+01:00','2021-01-07T16:55:05+01:00','UPS','','',64,3,NULL);
        INSERT INTO delivery VALUES(7,'DELIVERY','2021-01-05T09:58:16+01:00','2021-02-08T15:05:40+01:00','DHL','','',128,7,NULL);
        INSERT INTO delivery VALUES(8,'DELIVERY','2021-01-07T16:55:52+01:00','2021-02-04T07:51:05+01:00','TNT','','',64,3,NULL);
        INSERT INTO delivery VALUES(9,'DELIVERY','2021-01-13T14:08:37+01:00','2021-02-08T15:05:02+01:00','UPS','','',80,7,NULL);
        INSERT INTO delivery VALUES(10,'DELIVERY','2021-02-04T07:51:23+01:00','2021-02-08T15:05:44+01:00','Fedex','','',64,3,NULL);
        INSERT INTO delivery VALUES(11,'DELIVERY','2021-02-19T15:19:20+01:00',NULL,'PostNl','',NULL,80,7,NULL);
        INSERT INTO delivery VALUES(12,'DELIVERY','2021-03-15T10:15:16+01:00',NULL,'UPS','',NULL,128,3,NULL);
        INSERT INTO delivery VALUES(13,'DELIVERY','2021-03-26T12:25:14+01:00','2021-03-26T12:25:38+01:00','Bpost','','',64,7,NULL);
        COMMIT;
        """)

    def _assert_database_migration(self):
        # USERS
        user_orm = User.get_or_none(User.role == 'ADMIN')  # type: User
        self.assertEqual(None, user_orm.first_name)
        self.assertEqual(None, user_orm.last_name)
        self.assertIsNotNone(user_orm.username)
        self.assertIsNotNone(user_orm.password)
        self.assertEqual(1, user_orm.accepted_terms)
        self.assertEqual(1, user_orm.is_active)
        self.assertEqual('0000', user_orm.pin_code)
        self.assertEqual('en', user_orm.language)
        self.assertIsNone(user_orm.apartment)
        self.assertIsNone(user_orm.email)

        user_orm = User.get_or_none(User.role == 'TECHNICIAN')  # type: User
        self.assertEqual(None, user_orm.first_name)
        self.assertEqual(None, user_orm.last_name)
        self.assertIsNotNone(user_orm.username)
        self.assertIsNotNone(user_orm.password)
        self.assertEqual(1, user_orm.accepted_terms)
        self.assertEqual(1, user_orm.is_active)
        self.assertEqual('1111', user_orm.pin_code)
        self.assertEqual('en', user_orm.language)
        self.assertIsNone(user_orm.apartment)
        self.assertIsNone(user_orm.email)

        user_orm = User.get_or_none(User.first_name == 'pj')  # type: User
        self.assertEqual('pj', user_orm.first_name)
        self.assertEqual('t', user_orm.last_name)
        self.assertIsNotNone(user_orm.username)
        self.assertIsNotNone(user_orm.password)
        self.assertEqual(1, user_orm.accepted_terms)
        self.assertEqual(1, user_orm.is_active)
        self.assertEqual('5555', user_orm.pin_code)
        self.assertEqual('nl', user_orm.language)
        self.assertEqual('OM 1', user_orm.apartment.name)
        self.assertIsNone(user_orm.email)

        user_orm = User.get_or_none(User.first_name == 'Tesla')  # type: User
        self.assertEqual('Tesla', user_orm.first_name)
        self.assertEqual('Nikola', user_orm.last_name)
        self.assertIsNotNone(user_orm.username)
        self.assertIsNotNone(user_orm.password)
        self.assertEqual(1, user_orm.accepted_terms)
        self.assertEqual(1, user_orm.is_active)
        self.assertEqual('2222', user_orm.pin_code)
        self.assertEqual('en', user_orm.language)
        self.assertEqual('app 2', user_orm.apartment.name)
        self.assertIsNone(user_orm.email)

        user_orm = User.get_or_none(User.first_name == 'Thomas')  # type: User
        self.assertEqual('Thomas', user_orm.first_name)
        self.assertEqual('Edison', user_orm.last_name)
        self.assertIsNotNone(user_orm.username)
        self.assertIsNotNone(user_orm.password)
        self.assertEqual(1, user_orm.accepted_terms)
        self.assertEqual(0, user_orm.is_active)
        self.assertEqual('6666', user_orm.pin_code)
        self.assertEqual('de', user_orm.language)
        self.assertEqual('OM 1', user_orm.apartment.name)
        self.assertIsNone(user_orm.email)

        # APARTMENTS
        apartment_orm = Apartment.get_or_none(Apartment.name == 'OM 1')  # type: Apartment
        self.assertEqual(32, apartment_orm.mailbox_rebus_id)
        self.assertEqual(17, apartment_orm.doorbell_rebus_id)

        apartment_orm = Apartment.get_or_none(Apartment.name == 'app 2')  # type: Apartment
        self.assertEqual(48, apartment_orm.mailbox_rebus_id)
        self.assertEqual(18, apartment_orm.doorbell_rebus_id)

        # RFID
        rfid_orm = RFID.get_or_none(RFID.tag_string == 'RFIDTAG1')  # type: RFID
        self.assertEqual('RFIDTAG1', rfid_orm.tag_string)
        self.assertEqual('RFIDTAG1', rfid_orm.uid_manufacturer)
        self.assertEqual('', rfid_orm.uid_extension)
        self.assertEqual(-1, rfid_orm.enter_count)
        self.assertEqual(False, rfid_orm.blacklisted)
        self.assertEqual('test-tag-1', rfid_orm.label)
        self.assertEqual('2018-01-01T01:00:00+01:00', rfid_orm.timestamp_created)
        self.assertEqual('2021-01-29T15:10:00+01:00', rfid_orm.timestamp_last_used)
        self.assertEqual('pj', rfid_orm.user.first_name)

        rfid_orm = RFID.get_or_none(RFID.tag_string == 'RFIDTAG2')  # type: RFID
        self.assertEqual('RFIDTAG2', rfid_orm.tag_string)
        self.assertEqual('RFIDTAG2', rfid_orm.uid_manufacturer)
        self.assertEqual('', rfid_orm.uid_extension)
        self.assertEqual(-1, rfid_orm.enter_count)
        self.assertEqual(False, rfid_orm.blacklisted)
        self.assertEqual('test-tag-2', rfid_orm.label)
        self.assertEqual('2021-02-03T14:39:25+01:00', rfid_orm.timestamp_created)
        self.assertEqual('', rfid_orm.timestamp_last_used)
        self.assertEqual('Tesla', rfid_orm.user.first_name)

        rfid_orm = RFID.get_or_none(RFID.tag_string == 'RFIDTAG3')  # type: RFID
        self.assertEqual('RFIDTAG3', rfid_orm.tag_string)
        self.assertEqual('RFIDTAG3', rfid_orm.uid_manufacturer)
        self.assertEqual('RFIDEXT', rfid_orm.uid_extension)
        self.assertEqual(10, rfid_orm.enter_count)
        self.assertEqual(True, rfid_orm.blacklisted)
        self.assertEqual('test-tag-3', rfid_orm.label)
        self.assertEqual('2021-02-03T14:40:00+02:00', rfid_orm.timestamp_created)
        self.assertEqual('2021-01-29T15:11:00+01:00', rfid_orm.timestamp_last_used)
        self.assertEqual('Thomas', rfid_orm.user.first_name)

        # Delivery
        delivery_orm = Delivery.get_or_none(Delivery.timestamp_delivery == '2020-10-07T15:15:24+02:00')  # type: Delivery
        self.assertEqual('DELIVERY', delivery_orm.type)
        self.assertEqual('2020-10-07T15:15:24+02:00', delivery_orm.timestamp_delivery)
        self.assertEqual('2020-10-07T15:19:14+02:00', delivery_orm.timestamp_pickup)
        self.assertEqual('DPD', delivery_orm.courier_firm)
        self.assertEqual('Signature_Delivery', delivery_orm.signature_delivery)
        self.assertEqual('Signature_pickup', delivery_orm.signature_pickup)
        self.assertEqual(128, delivery_orm.parcelbox_rebus_id)
        self.assertEqual('pj', delivery_orm.user_pickup.first_name)
        self.assertIsNone(delivery_orm.user_delivery)

        delivery_orm = Delivery.get_or_none(Delivery.timestamp_delivery == '2020-10-07T15:16:49+02:00')  # type: Delivery
        self.assertEqual('DELIVERY', delivery_orm.type)
        self.assertEqual('2020-10-07T15:16:49+02:00', delivery_orm.timestamp_delivery)
        self.assertEqual('2021-01-07T16:54:55+01:00', delivery_orm.timestamp_pickup)
        self.assertEqual('UPS', delivery_orm.courier_firm)
        self.assertEqual('', delivery_orm.signature_delivery)
        self.assertEqual('', delivery_orm.signature_pickup)
        self.assertEqual(80, delivery_orm.parcelbox_rebus_id)
        self.assertEqual('Tesla', delivery_orm.user_pickup.first_name)
        self.assertIsNone(delivery_orm.user_delivery)

        delivery_orm = Delivery.get_or_none(Delivery.timestamp_delivery == '2020-10-07T15:28:19+02:00')  # type: Delivery
        self.assertEqual('RETURN', delivery_orm.type)
        self.assertEqual('2020-10-07T15:28:19+02:00', delivery_orm.timestamp_delivery)
        self.assertEqual('2020-10-07T15:28:42+02:00', delivery_orm.timestamp_pickup)
        self.assertIsNone(delivery_orm.courier_firm)
        self.assertEqual('', delivery_orm.signature_delivery)
        self.assertEqual('', delivery_orm.signature_pickup)
        self.assertEqual(128, delivery_orm.parcelbox_rebus_id)
        self.assertEqual('ADMIN', delivery_orm.user_pickup.role)
        self.assertIsNone(delivery_orm.user_delivery)

        delivery_orm = Delivery.get_or_none(Delivery.timestamp_delivery == '2020-11-24T16:39:15+01:00')  # type: Delivery
        self.assertEqual('DELIVERY', delivery_orm.type)
        self.assertEqual('2020-11-24T16:39:15+01:00', delivery_orm.timestamp_delivery)
        self.assertIsNone(delivery_orm.timestamp_pickup)
        self.assertIsNone(delivery_orm.courier_firm)
        self.assertEqual('', delivery_orm.signature_delivery)
        self.assertEqual('', delivery_orm.signature_pickup)
        self.assertEqual(128, delivery_orm.parcelbox_rebus_id)
        self.assertEqual('pj', delivery_orm.user_pickup.first_name)
        self.assertIsNone(delivery_orm.user_delivery)

        # CONFIG
        doorbell_config = Config.get_entry('doorbell_config', None)
        self.assertEqual({
            'enabled': True
        }, doorbell_config)

        rfid_config = Config.get_entry('rfid_config', None)
        self.assertEqual({
            'enabled': True,
            'max_tags': 4,
            'security_enabled': False
        }, rfid_config)

        rfid_sector_block_config = Config.get_entry('rfid_sector_block_config', None)
        self.assertEqual({
            'rfid_sector_block': 1,
        }, rfid_sector_block_config)

        global_config = Config.get_entry('global_config', None)
        self.assertEqual({
            'device_name': 'ESAFE[]',
            'country': 'BE',
            'postal_code': '',
            'city': '',
            'street': 'vgs',
            'house_number': '52',
            'language': 'en'
        }, global_config)

        activate_user_config = Config.get_entry('activate_user_config', None)
        self.assertEqual({
            'change_first_name': True,
            'change_last_name': True,
            'change_language': True,
            'change_pin_code': False
        }, activate_user_config)

    def test_migrate_to_empty(self):
        print(os.environ['OPENMOTICS_PREFIX'])
        self.log("Testing eSafe migration to empty database")
        self._create_esafe_database_dummy_data()
        EsafeMigrator.migrate()
        self._assert_database_migration()

    def test_migrate_to_filled(self):
        print(os.environ['OPENMOTICS_PREFIX'])
        self.log("Testing eSafe migration to filled database")
        self._create_esafe_database_dummy_data()

        # Adding some users
        # ---------------------------
        def save_user(user_dto):
            user_orm = UserMapper.dto_to_orm(user_dto)
            user_orm.save()
        # Typical setup of users (only super users)
        user_1 = UserDTO(username='test_user_1', first_name='tester', last_name='user', role=User.UserRoles.SUPER, accepted_terms=1, is_active=True).set_password('test')
        save_user(user_1)
        user_2 = UserDTO(username='test_user_2', first_name='tester', last_name='user2', role=User.UserRoles.SUPER, accepted_terms=1, is_active=True).set_password('test')
        save_user(user_2)
        user_3 = UserDTO(username='test_user_3', first_name='tester', last_name='user3', role=User.UserRoles.SUPER, accepted_terms=1, is_active=True).set_password('test')
        save_user(user_3)

        # Adding some apartments
        # ---------------------------
        def save_apartment(apartment_dto):
            apartment_orm = ApartmentMapper.dto_to_orm(apartment_dto)
            apartment_orm.save()
        save_apartment(ApartmentDTO(name='app 1'))
        save_apartment(ApartmentDTO(name='app 2', mailbox_rebus_id=37, doorbell_rebus_id=38))
        
        # Adding some rfid tags
        # ---------------------------
        def save_rfid(rfid_dto):
            self.rfid_controller.save_rfid(rfid_dto)
        save_rfid(RfidDTO(tag_string='RFIDTAG1', uid_manufacturer='RFIDTAG1', label='test-rfid', enter_count=-1, user=user_1))
        save_rfid(RfidDTO(tag_string='RFIDTAG2', uid_manufacturer='RFIDTAG2', label='test-rfid', enter_count=10, blacklisted=True, user=user_2))

        EsafeMigrator.migrate()
        self._assert_database_migration()

