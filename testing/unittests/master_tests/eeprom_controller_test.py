# Copyright (C) 2016 OpenMotics BV
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
Tests for the eeprom_controller module.
"""

from __future__ import absolute_import

import os
import unittest

import mock

import master.classic.master_api as master_api
from gateway.hal.master_event import MasterEvent
from gateway.pubsub import PubSub
from ioc import INJECTED, Inject, SetTestMode, SetUpTestInjections
from master.classic.eeprom_controller import CompositeDataType, \
    EepromActions, EepromAddress, EepromByte, EepromController, EepromData, \
    EepromFile, EepromIBool, EepromId, EepromModel, EepromSignedTemp, \
    EepromString, EepromWord, EextByte, EextString
from master.classic.eeprom_extension import EepromExtension


class Model1(EepromModel):
    """ Dummy model with an id. """
    id = EepromId(10)
    name = EepromString(100, lambda id: (1, 2 + id))


class Model2(EepromModel):
    """ Dummy model without an id. """
    name = EepromString(100, (3, 4))


class Model3(EepromModel):
    """ Dummy model with multiple fields. """
    name = EepromString(10, (3, 4))
    link = EepromByte((3, 14))
    out = EepromWord((3, 15))


class Model4(EepromModel):
    """ Dummy model with a dynamic maximum id. """
    id = EepromId(10, address=EepromAddress(0, 0, 1), multiplier=2)
    name = EepromString(10, lambda id: (1, 2 + id * 10))


class Model5(EepromModel):
    """ Dummy model with multiple fields and an id. """
    id = EepromId(3)
    name = EepromString(10, lambda id: (3+id, 4))
    link = EepromByte(lambda id: (3+id, 14))
    out = EepromWord(lambda id: (3+id, 15))


class Model6(EepromModel):
    """ Dummy model with a CompositeDataType. """
    name = EepromString(10, (3, 4))
    status = CompositeDataType([('link', EepromByte((3, 14))),
                                ('out', EepromWord((3, 15)))])


class Model7(EepromModel):
    """ Dummy model with multiple fields, including eext fields and an id. """
    id = EepromId(3)
    name = EepromString(10, lambda id: (id, 4))
    link = EepromByte(lambda id: (id, 14))
    room = EextByte()


class Model8(EepromModel):
    """ Dummy model with multiple fields, including eext fields, without an id. """
    name = EepromString(10, (1, 4))
    link = EepromByte((1, 14))
    room = EextByte()


class Model9(EepromModel):
    """ Dummy model with multiple fields, including eext fields, without an id. """
    id = EepromId(10)
    name = EextString()
    foo = EextByte()


def get_eeprom_file_dummy(banks):
    """ Create an EepromFile when the data for all banks is provided.

    :param banks: list of basestring
    """
    def list_fct(data):
        """ Dummy for listing a bank. """
        return {'data': banks[data['bank']]}

    def write_fct(data):
        """ Dummy for writing bytes to a bank. """
        bank = banks[data['bank']]
        address = data['address']
        data_bytes = data['data']

        banks[data['bank']] = bank[0:address] + data_bytes + bank[address+len(data_bytes):]

    SetUpTestInjections(master_communicator=MasterCommunicator(list_fct, write_fct))
    return EepromFile()


EEPROM_DB_FILE = 'test.db'


def get_eeprom_controller_dummy(banks):
    """ Create a dummy EepromController, banks is passed to get_eeprom_file_dummy. """
    SetUpTestInjections(pubsub=PubSub())
    SetUpTestInjections(eeprom_file=get_eeprom_file_dummy(banks),
                        eeprom_db=EEPROM_DB_FILE)
    SetUpTestInjections(eeprom_extension=EepromExtension())
    return EepromController()


@Inject
def get_pubsub(pubsub=INJECTED):
    return pubsub


class EepromControllerTest(unittest.TestCase):
    """ Tests for EepromController. """

    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):  # pylint: disable=C0103
        """ Run before each test. """
        if os.path.exists(EEPROM_DB_FILE):
            os.remove(EEPROM_DB_FILE)

    def tearDown(self):  # pylint: disable=C0103
        """ Run after each test. """
        if os.path.exists(EEPROM_DB_FILE):
            os.remove(EEPROM_DB_FILE)

    def test_read(self):
        """ Test read. """
        controller = get_eeprom_controller_dummy({0: bytearray([0] * 256),
                                                  1: bytearray([0] * 2) + bytearray(b'hello') + bytearray([0] * 249)})
        model = controller.read(Model1, 0)
        self.assertEqual(0, model.id)
        self.assertEqual('hello' + '\x00' * 95, model.name)

        controller = get_eeprom_controller_dummy({3: bytearray([0] * 4) + bytearray(b'hello') + bytearray([0] * 247)})
        model = controller.read(Model2)
        self.assertEqual('hello' + '\x00' * 95, model.name)

    def test_read_field(self):
        """ Test read with a field. """
        controller = get_eeprom_controller_dummy({3: bytearray([0] * 4) + bytearray(b'helloworld') + bytearray([1, 2, 0] + [0] * 239)})
        model = controller.read(Model5, 0, [u'name'])
        self.assertEqual(0, model.id)
        self.assertEqual('helloworld', model.name)
        self.assertFalse('link' in model.__dict__)
        self.assertFalse('out' in model.__dict__)

        model = controller.read(Model5, 0, ['name', 'link'])
        self.assertEqual(0, model.id)
        self.assertEqual('helloworld', model.name)
        self.assertEqual(1, model.link)
        self.assertFalse('out' in model.__dict__)

        model = controller.read(Model5, 0, ['name', 'out'])
        self.assertEqual(0, model.id)
        self.assertEqual('helloworld', model.name)
        self.assertFalse('link' in model.__dict__)
        self.assertEqual(2, model.out)

        model = controller.read(Model5, 0, ['name', 'out', 'link'])
        self.assertEqual(0, model.id)
        self.assertEqual('helloworld', model.name)
        self.assertEqual(1, model.link)
        self.assertEqual(2, model.out)

    def test_read_batch(self):
        """ Test read_batch. """
        controller = get_eeprom_controller_dummy({0: bytearray([0] * 256),
                                                  1: bytearray([0] * 2) + bytearray(b'hello') + bytearray([0] * 249)})
        models = controller.read_batch(Model1, [0, 3, 8])

        self.assertEqual(3, len(models))

        self.assertEqual(0, models[0].id)
        self.assertEqual('hello' + '\x00' * 95, models[0].name)

        self.assertEqual(3, models[1].id)
        self.assertEqual('lo' + '\x00' * 98, models[1].name)

        self.assertEqual(8, models[2].id)
        self.assertEqual('\x00' * 100, models[2].name)

    def test_read_batch_field(self):
        """ Test read_batch with a field. """
        controller = get_eeprom_controller_dummy({3: bytearray([0] * 4) + bytearray(b'helloworld') + bytearray([1, 0, 2] + [0] * 239),
                                                  4: bytearray([0] * 4) + bytearray(b'secondpage') + bytearray([2, 0, 3] + [0] * 239)})
        models = controller.read_batch(Model5, [0, 1], ['name'])

        self.assertEqual(2, len(models))

        self.assertEqual(0, models[0].id)
        self.assertEqual('helloworld', models[0].name)
        self.assertFalse('link' in models[0].__dict__)
        self.assertFalse('out' in models[0].__dict__)

        self.assertEqual(1, models[1].id)
        self.assertEqual('secondpage', models[1].name)
        self.assertFalse('link' in models[1].__dict__)
        self.assertFalse('out' in models[1].__dict__)

    def test_read_all_without_id(self):
        """ Test read_all for EepromModel without id. """
        controller = get_eeprom_controller_dummy([])

        with self.assertRaises(TypeError) as ex:
            controller.read_all(Model2)
        self.assertTrue('id' in str(ex.exception))

    def test_read_all(self):
        """ Test read_all. """
        controller = get_eeprom_controller_dummy({0: bytearray([0] * 256),
                                                  1: bytearray([0] * 2) + bytearray(b'hello') + bytearray([0] * 249)})
        models = controller.read_all(Model1)

        self.assertEqual(10, len(models))
        self.assertEqual('hello' + '\x00' * 95, models[0].name)
        self.assertEqual('ello' + '\x00' * 96, models[1].name)
        self.assertEqual('llo' + '\x00' * 97, models[2].name)
        self.assertEqual('lo' + '\x00' * 98, models[3].name)
        self.assertEqual('o' + '\x00' * 99, models[4].name)
        self.assertEqual('\x00' * 100, models[5].name)
        self.assertEqual('\x00' * 100, models[6].name)
        self.assertEqual('\x00' * 100, models[7].name)
        self.assertEqual('\x00' * 100, models[8].name)
        self.assertEqual('\x00' * 100, models[9].name)

    def test_read_all_fields(self):
        """ Test read_all with a field. """
        controller = get_eeprom_controller_dummy({3: bytearray([0] * 4) + bytearray(b'helloworld') + bytearray([1, 0, 2] + [0] * 239),
                                                  4: bytearray([0] * 4) + bytearray(b'secondpage') + bytearray([2, 0, 3] + [0] * 239),
                                                  5: bytearray([0] * 4) + bytearray(b'anotherone') + bytearray([4, 0, 5] + [0] * 239)})

        models = controller.read_all(Model5, ['name', 'link'])

        self.assertEqual(3, len(models))

        self.assertEqual(0, models[0].id)
        self.assertEqual('helloworld', models[0].name)
        self.assertEqual(1, models[0].link)
        self.assertFalse('out' in models[0].__dict__)

        self.assertEqual(1, models[1].id)
        self.assertEqual('secondpage', models[1].name)
        self.assertEqual(2, models[1].link)
        self.assertFalse('out' in models[1].__dict__)

        self.assertEqual(2, models[2].id)
        self.assertEqual('anotherone', models[2].name)
        self.assertEqual(4, models[2].link)
        self.assertFalse('out' in models[2].__dict__)

    def test_get_max_id(self):
        """ Test get_max_id. """
        controller = get_eeprom_controller_dummy({0: bytearray([5] + [0] * 254)})
        self.assertEqual(9, Model4.get_max_id(controller._eeprom_file))

        controller = get_eeprom_controller_dummy({0: bytearray([16] + [0] * 254)})
        self.assertEqual(31, Model4.get_max_id(controller._eeprom_file))

        controller = get_eeprom_controller_dummy({})
        self.assertEqual(9, Model1.get_max_id(controller._eeprom_file))

        with self.assertRaises(TypeError) as ex:
            Model2.get_max_id(controller._eeprom_file)
        self.assertTrue('id' in str(ex.exception))

    def test_write(self):
        """ Test write. """
        controller = get_eeprom_controller_dummy({0: bytearray([0] * 256),
                                                  1: bytearray([0] * 256),
                                                  2: bytearray([0] * 256),
                                                  3: bytearray([0] * 256)})
        controller.write(Model1.deserialize({'id': 1, 'name': 'Hello world !' + '\xff' * 10}))

        model = controller.read(Model1, 1)
        self.assertEqual(1, model.id)
        self.assertEqual('Hello world !', model.name)

    def test_write_sparse(self):
        """ Test write when not all fields of the model are provided. """
        controller = get_eeprom_controller_dummy({0: bytearray([0] * 256),
                                                  1: bytearray([0] * 256),
                                                  2: bytearray([0] * 256),
                                                  3: bytearray([0] * 256)})
        controller.write(Model5.deserialize({'id': 0, 'name': 'Helloworld'}))

        model = controller.read(Model5, 0)
        self.assertEqual(0, model.id)
        self.assertEqual('Helloworld', model.name)
        self.assertEqual(0, model.link)
        self.assertEqual(0, model.out)

        controller.write(Model5.deserialize({'id': 0, 'name': 'Helloworld', 'link': 1}))

        model = controller.read(Model5, 0)
        self.assertEqual(0, model.id)
        self.assertEqual('Helloworld', model.name)
        self.assertEqual(1, model.link)
        self.assertEqual(0, model.out)

    def test_write_batch_one(self):
        """ Test write_batch with one model. """
        controller = get_eeprom_controller_dummy({0: bytearray([0] * 256),
                                                  1: bytearray([0] * 256),
                                                  2: bytearray([0] * 256),
                                                  3: bytearray([0] * 256)})
        controller.write_batch([Model1.deserialize({'id': 3, 'name': 'Hello world !'})])

        model = controller.read(Model1, 3)
        self.assertEqual(3, model.id)
        self.assertEqual('Hello world !', model.name)

    def test_write_batch_multiple(self):
        """ Test write with multiple models. """
        controller = get_eeprom_controller_dummy({0: bytearray([0] * 256),
                                                  1: bytearray([0] * 256),
                                                  2: bytearray([0] * 256),
                                                  3: bytearray([0] * 256)})
        controller.write_batch([Model1.deserialize({'id': 3, 'name': 'First model'}),
                                Model2.deserialize({'name': 'Second model' + '\x01' * 88})])

        model = controller.read(Model1, 3)
        self.assertEqual(3, model.id)
        self.assertEqual('First model', model.name)

        model = controller.read(Model2)
        self.assertEqual('Second model' + '\x01' * 88, model.name)

    def test_read_with_ext(self):
        """ Test reading a model with an EextDataType. """
        controller = get_eeprom_controller_dummy({0: bytearray([0] * 256),
                                                  1: bytearray([0] * 256),
                                                  2: bytearray([0] * 256),
                                                  3: bytearray([0] * 256)})
        model7 = controller.read(Model7, 1)

        self.assertEqual(1, model7.id)
        self.assertEqual('\x00'*10, model7.name)
        self.assertEqual(0, model7.link)
        self.assertEqual(255, model7.room)

    def test_read_batch_with_ext(self):
        """ Test reading a batch of models with an EextDataType. """
        controller = get_eeprom_controller_dummy({0: bytearray([0] * 256),
                                                  1: bytearray([0] * 256),
                                                  2: bytearray([0] * 256),
                                                  3: bytearray([0] * 256)})
        models = controller.read_batch(Model7, [1, 2])

        self.assertEqual(1, models[0].id)
        self.assertEqual('\x00'*10, models[0].name)
        self.assertEqual(0, models[0].link)
        self.assertEqual(255, models[0].room)

        self.assertEqual(2, models[1].id)
        self.assertEqual('\x00'*10, models[1].name)
        self.assertEqual(0, models[1].link)
        self.assertEqual(255, models[1].room)

    def test_write_read_with_ext(self):
        """ Test writing and reading a model with an EextDataType. """
        controller = get_eeprom_controller_dummy({0: bytearray([255] * 256),
                                                  1: bytearray([255] * 256),
                                                  2: bytearray([255] * 256),
                                                  3: bytearray([255] * 256)})
        controller.write_batch([Model7.deserialize({'id': 1, 'name': 'First', 'link': 79, 'room': 123}),
                                Model7.deserialize({'id': 2, 'name': 'Second', 'link': 99, 'room': 55})])

        models = controller.read_batch(Model7, [1, 2])

        self.assertEqual(1, models[0].id)
        self.assertEqual('First', models[0].name)
        self.assertEqual(79, models[0].link)
        self.assertEqual(123, models[0].room)

        self.assertEqual(2, models[1].id)
        self.assertEqual('Second', models[1].name)
        self.assertEqual(99, models[1].link)
        self.assertEqual(55, models[1].room)

    def test_write_read_with_ext_without_id(self):
        """ Test writing and reading a model with an EextDataType but without id. """
        controller = get_eeprom_controller_dummy({0: bytearray([255] * 256),
                                                  1: bytearray([255] * 256),
                                                  2: bytearray([255] * 256),
                                                  3: bytearray([255] * 256)})
        controller.write(Model8.deserialize({'name': 'First', 'link': 79, 'room': 123}))

        model8 = controller.read(Model8)

        self.assertEqual('First', model8.name)
        self.assertEqual(79, model8.link)
        self.assertEqual(123, model8.room)

    def test_ext_only(self):
        """ Test writing and reading a model that only has an id and EextDataType fields. """
        controller = get_eeprom_controller_dummy({})
        ids = Model9.id.get_max_id() + 1

        batch = []
        for i in range(ids):
            batch.append(Model9.deserialize({'id': i, 'name': 'Room {0}'.format(i), 'foo': i // 2}))

        controller.write_batch(batch)

        models = controller.read_all(Model9)

        self.assertEqual(ids, len(models))
        for i in range(ids):
            self.assertEqual(i, models[i].id)
            self.assertEqual('Room {0}'.format(i), models[i].name)
            self.assertEqual(i // 2, models[i].foo)

    def test_eeprom_events(self):
        """ Test read. """
        controller = get_eeprom_controller_dummy({0: bytearray([0] * 256),
                                                  1: bytearray([0] * 2) + bytearray(b'hello') + bytearray([0] * 249)})
        model = controller.read(Model1, 0)
        self.assertEqual(0, model.id)
        self.assertEqual('hello' + '\x00' * 95, model.name)

        events = []

        def handle_events(master_event):
            events.append(master_event)

        get_pubsub().subscribe_master_events(PubSub.MasterTopics.EEPROM, handle_events)
        controller.invalidate_cache()
        get_pubsub()._publish_all_events(blocking=False)
        self.assertEqual([
            MasterEvent(MasterEvent.Types.EEPROM_CHANGE, {})
        ], events)
        controller.activate()
        get_pubsub()._publish_all_events(blocking=False)
        self.assertEqual([
            MasterEvent(MasterEvent.Types.EEPROM_CHANGE, {}),
            MasterEvent(MasterEvent.Types.EEPROM_CHANGE, {})
        ], events)


class MasterCommunicator(object):
    """ Dummy for the MasterCommunicator. """

    def __init__(self, list_function=None, write_function=None):
        """ Default constructor. """
        self.__list_function = list_function
        self.__write_function = write_function

    def do_command(self, cmd, data, timeout=None):
        """ Execute a command on the master dummy. """
        if cmd == master_api.eeprom_list():
            return self.__list_function(data)
        elif cmd == master_api.read_eeprom():
            bank = self.__list_function(data)['data']
            return {'data': bank[data['addr']: data['addr'] + data['num']]}
        elif cmd == master_api.write_eeprom():
            return self.__write_function(data)
        elif cmd == master_api.activate_eeprom():
            return {'eep': 0, 'resp': 'OK'}
        else:
            raise Exception('Command {0} not found'.format(cmd))


class EepromFileTest(unittest.TestCase):
    """ Tests for EepromFile. """

    def test_read_one_bank_one_address(self):
        """ Test read from one bank with one address """
        def read(_data):
            """ Read dummy. """
            if _data['bank'] == 1:
                return {'data': bytearray(b'abc') + bytearray([255] * 200) + bytearray(b'def') + bytearray([255] * 48)}
            else:
                raise Exception('Wrong page')
        SetUpTestInjections(master_communicator=MasterCommunicator(read))

        eeprom_file = EepromFile()
        address = EepromAddress(1, 0, 3)
        data = eeprom_file.read([address])

        self.assertEqual(1, len(data))
        self.assertEqual(address, data[address].address)
        self.assertEqual(bytearray(b'abc'), data[address].bytes)

    def test_read_one_bank_two_addresses(self):
        """ Test read from one bank with two addresses. """
        def read(_data):
            """ Read dummy """
            if _data['bank'] == 1:
                return {'data': bytearray(b'abc') + bytearray([255] * 200) + bytearray(b'def') + bytearray([255] * 48)}
            else:
                raise Exception('Wrong page')
        SetUpTestInjections(master_communicator=MasterCommunicator(read))

        eeprom_file = EepromFile()

        address1 = EepromAddress(1, 2, 10)
        address2 = EepromAddress(1, 203, 4)
        data = eeprom_file.read([address1, address2])

        self.assertEqual(2, len(data))

        self.assertEqual(address1, data[address1].address)
        self.assertEqual(bytearray(b'c') + bytearray([255] * 9), data[address1].bytes)

        self.assertEqual(address2, data[address2].address)
        self.assertEqual(bytearray(b'def\xff'), data[address2].bytes)

    def test_read_multiple_banks(self):
        """ Test read from multiple banks. """
        def read(_data):
            """ Read dummy. """
            if _data['bank'] == 1:
                return {'data': bytearray(b'abc') + bytearray([255] * 200) + bytearray(b'def') + bytearray([255] * 48)}
            if _data['bank'] == 100:
                return {'data': bytearray(b'hello') + bytearray([0] * 100) + bytearray(b'world') + bytearray([0] * 146)}
            else:
                raise Exception('Wrong page')
        SetUpTestInjections(master_communicator=MasterCommunicator(read))

        eeprom_file = EepromFile()

        address1 = EepromAddress(1, 2, 10)
        address2 = EepromAddress(100, 4, 10)
        address3 = EepromAddress(100, 105, 5)
        data = eeprom_file.read([address1, address2, address3])

        self.assertEqual(3, len(data))

        self.assertEqual(address1, data[address1].address)
        self.assertEqual(bytearray(b'c') + bytearray([255] * 9), data[address1].bytes)

        self.assertEqual(address2, data[address2].address)
        self.assertEqual(bytearray(b'o') + bytearray([0] * 9), data[address2].bytes)

        self.assertEqual(address3, data[address3].address)
        self.assertEqual(bytearray(b'world'), data[address3].bytes)

    def test_write_single_field(self):
        """ Write a single field to the eeprom file. """
        done = {}

        def read(data):
            """ Read dummy. """
            if data['bank'] == 1:
                done['read1'] = True
                return {'data': bytearray([255] * 256)}
            else:
                raise Exception('Wrong page')

        def write(data):
            """ Write dummy. """
            self.assertEqual(1, data['bank'])
            self.assertEqual(2, data['address'])
            self.assertEqual(bytearray(b'abc'), data['data'])
            done['write'] = True

        SetUpTestInjections(master_communicator=MasterCommunicator(read, write))

        eeprom_file = EepromFile()
        eeprom_file.write([EepromData(EepromAddress(1, 2, 3), bytearray(b'abc'))])

        self.assertTrue('read1' in done)
        self.assertTrue('write' in done)

    def test_write_multiple_fields(self):
        """ Test writing multiple fields to the eeprom file. """
        done = {}

        def read(data):
            """ Read dummy. """
            if data['bank'] == 1:
                done['read1'] = True
                return {'data': bytearray([255] * 256)}
            elif data['bank'] == 2:
                done['read2'] = True
                return {'data': bytearray([0] * 256)}
            else:
                raise Exception('Wrong page')

        def write(data):
            """ Write dummy. """
            if 'write1' not in done:
                done['write1'] = True
                self.assertEqual(1, data['bank'])
                self.assertEqual(2, data['address'])
                self.assertEqual(bytearray(b'abc'), data['data'])
            elif 'write2' not in done:
                done['write2'] = True
                self.assertEqual(2, data['bank'])
                self.assertEqual(123, data['address'])
                self.assertEqual(bytearray(b'More bytes'), data['data'])
            elif 'write3' not in done:
                done['write3'] = True
                self.assertEqual(2, data['bank'])
                self.assertEqual(133, data['address'])
                self.assertEqual(bytearray(b' than 10'), data['data'])
            else:
                raise Exception('Too many writes')

        SetUpTestInjections(master_communicator=MasterCommunicator(read, write))

        eeprom_file = EepromFile()
        eeprom_file.write([EepromData(EepromAddress(1, 2, 3), bytearray(b'abc')),
                           EepromData(EepromAddress(2, 123, 18), bytearray(b'More bytes than 10'))])

        self.assertTrue('read1' in done)
        self.assertTrue('read2' in done)
        self.assertTrue('write1' in done)
        self.assertTrue('write2' in done)
        self.assertTrue('write3' in done)

    def test_write_multiple_fields_same_batch(self):
        """ Test writing multiple fields to the eeprom file. """
        done = {}

        def read(data):
            """ Read dummy. """
            if data['bank'] == 1:
                done['read'] = True
                return {'data': bytearray([255] * 256)}
            else:
                raise Exception('Wrong page')

        def write(data):
            """ Write dummy. """
            if 'write1' not in done:
                done['write1'] = True
                self.assertEqual(1, data['bank'])
                self.assertEqual(2, data['address'])
                self.assertEqual(bytearray(b'abc') + bytearray([255] * 3) + bytearray(b'defg'), data['data'])
            elif 'write2' not in done:
                done['write2'] = True
                self.assertEqual(1, data['bank'])
                self.assertEqual(12, data['address'])
                self.assertEqual(bytearray(b'hijklmn'), data['data'])
            else:
                raise Exception('Too many writes')

        SetUpTestInjections(master_communicator=MasterCommunicator(read, write))

        eeprom_file = EepromFile()
        eeprom_file.write([EepromData(EepromAddress(1, 2, 3), bytearray(b'abc')),
                           EepromData(EepromAddress(1, 8, 11), bytearray(b'defghijklmn'))])

        self.assertTrue('read' in done)
        self.assertTrue('write1' in done)
        self.assertTrue('write2' in done)

    def test_cache(self):
        """ Test the caching of banks. """
        state = {'count': 0}

        def read(_):
            """ Read dummy. """
            if state['count'] == 0:
                state['count'] = 1
                return {'data': bytearray([255] * 256)}
            else:
                raise Exception('Too many reads !')
        SetUpTestInjections(master_communicator=MasterCommunicator(read))

        eeprom_file = EepromFile()
        address = EepromAddress(1, 0, 256)
        read = eeprom_file.read([address])
        self.assertEqual(bytearray([255] * 256), read[address].bytes)

        # Second read should come from cache, if read is called
        # an exception will be thrown.
        address = EepromAddress(1, 0, 256)
        read = eeprom_file.read([address])
        self.assertEqual(bytearray([255] * 256), read[address].bytes)

    def test_cache_invalidate(self):
        """ Test the cache invalidation. """
        state = {'count': 0}

        def read(_):
            """ Read dummy. """
            if state['count'] == 0:
                state['count'] = 1
                return {'data': bytearray([255] * 256)}
            elif state['count'] == 1:
                state['count'] = 2
                return {'data': bytearray([255] * 256)}
            else:
                raise Exception('Too many reads !')

        SetUpTestInjections(master_communicator=MasterCommunicator(read))

        eeprom_file = EepromFile()
        address = EepromAddress(1, 0, 256)
        read = eeprom_file.read([address])
        self.assertEqual(bytearray([255] * 256), read[address].bytes)

        # Second read should come from cache.
        address = EepromAddress(1, 0, 256)
        read = eeprom_file.read([address])
        self.assertEqual(bytearray([255] * 256), read[address].bytes)

        eeprom_file.invalidate_cache()
        # Should be read from communicator, since cache is invalid
        address = EepromAddress(1, 0, 256)
        read = eeprom_file.read([address])
        self.assertEqual(bytearray([255] * 256), read[address].bytes)

        self.assertEqual(2, state['count'])

    def test_cache_write(self):
        """ Test the eeprom cache on writing. """
        state = {'read': 0, 'write': 0}

        def read(_):
            """ Read dummy. """
            if state['read'] == 0:
                state['read'] = 1
                return {'data': bytearray([255] * 256)}
            else:
                raise Exception('Too many reads !')

        def write(data):
            """ Write dummy. """
            if state['write'] == 0:
                self.assertEqual(1, data['bank'])
                self.assertEqual(100, data['address'])
                self.assertEqual(bytearray([0] * 10), data['data'])
                state['write'] = 1
            elif state['write'] == 1:
                self.assertEqual(1, data['bank'])
                self.assertEqual(110, data['address'])
                self.assertEqual(bytearray([0] * 10), data['data'])
                state['write'] = 2
            else:
                raise Exception('Too many writes !')

        SetUpTestInjections(master_communicator=MasterCommunicator(read, write))

        eeprom_file = EepromFile()

        address = EepromAddress(1, 0, 256)
        read = eeprom_file.read([address])
        self.assertEqual(bytearray([255] * 256), read[address].bytes)

        eeprom_file.write([EepromData(EepromAddress(1, 100, 20), bytearray([0] * 20))])

        address = EepromAddress(1, 0, 256)
        read = eeprom_file.read([address])
        self.assertEqual(bytearray([255] * 100 + [0] * 20 + [255] * 136), read[address].bytes)

        self.assertEqual(1, state['read'])
        self.assertEqual(2, state['write'])

    def test_cache_write_exception(self):
        """ The cache should be invalidated if a write fails. """
        state = {'read': 0, 'write': 0}

        def read(_):
            """ Read dummy. """
            if state['read'] == 0:
                state['read'] = 1
                return {'data': bytearray([255] * 256)}
            elif state['read'] == 1:
                state['read'] = 2
                return {'data': bytearray([255] * 256)}
            else:
                raise Exception('Too many reads !')

        def write(_):
            """ Write dummy. """
            state['write'] += 1
            raise Exception('write fails...')

        SetUpTestInjections(master_communicator=MasterCommunicator(read, write))

        eeprom_file = EepromFile()

        address = EepromAddress(1, 0, 256)
        read = eeprom_file.read([address])
        self.assertEqual(bytearray([255] * 256), read[address].bytes)

        try:
            eeprom_file.write([EepromData(EepromAddress(1, 100, 20), bytearray([0] * 20))])
            self.fail('Should not get here !')
        except Exception:
            pass

        address = EepromAddress(1, 0, 256)
        read = eeprom_file.read([address])
        self.assertEqual(bytearray([255] * 256), read[address].bytes)

        self.assertEqual(2, state['read'])
        self.assertEqual(1, state['write'])

    def test_write_end_of_page(self):
        """ Test writing an address that is close (< BATCH_SIZE) to the end of the page. """
        done = {}

        def read(_):
            """ Read dummy. """
            return {'data': bytearray([0] * 256)}

        def write(data):
            """ Write dummy. """
            self.assertEqual(117, data['bank'])
            self.assertEqual(248, data['address'])
            self.assertEqual(bytearray(b'test') + bytearray([255] * 4), data['data'])
            done['done'] = True

        SetUpTestInjections(master_communicator=MasterCommunicator(read, write))

        eeprom_file = EepromFile()
        eeprom_file.write([EepromData(EepromAddress(117, 248, 8), bytearray(b'test') + bytearray([255] * 4))])
        self.assertTrue(done['done'])


class EepromModelTest(unittest.TestCase):
    """ Tests for EepromModel. """

    def test_get_fields(self):
        """ Test get_fields. """
        fields = Model1.get_fields(include_eeprom=True)

        self.assertEqual(1, len(fields))
        self.assertEqual('name', fields[0][0])

        fields = Model1.get_fields(include_id=True, include_eeprom=True)

        self.assertEqual(2, len(fields))
        self.assertEqual('id', fields[0][0])
        self.assertEqual('name', fields[1][0])

        fields = Model6.get_fields(include_eeprom=True)

        self.assertEqual(2, len(fields))
        self.assertEqual('name', fields[0][0])
        self.assertEqual('status', fields[1][0])

        fields = Model7.get_fields(include_id=True, include_eeprom=True)

        self.assertEqual(3, len(fields))
        self.assertEqual('id', fields[0][0])
        self.assertEqual('link', fields[1][0])
        self.assertEqual('name', fields[2][0])

        fields = Model7.get_fields(include_id=True, include_eeprom=True, include_eext=True)

        self.assertEqual(4, len(fields))
        self.assertEqual('id', fields[0][0])
        self.assertEqual('link', fields[1][0])
        self.assertEqual('name', fields[2][0])
        self.assertEqual('room', fields[3][0])

    def test_has_id(self):
        """ Test has_id. """
        self.assertTrue(Model1.has_id())
        self.assertFalse(Model2.has_id())
        self.assertTrue(Model7.has_id())
        self.assertFalse(Model8.has_id())

    def test_get_name(self):
        """ Test get_name. """
        self.assertEqual('Model1', Model1.get_name())
        self.assertEqual('Model2', Model2.get_name())

    def test_check_id(self):
        """ Test check_id. """
        Model1.check_id(0)  # Should just work

        with self.assertRaises(TypeError) as ex:
            Model1.check_id(100)
        self.assertTrue('maximum' in str(ex.exception))

        with self.assertRaises(TypeError) as ex:
            Model1.check_id(None)
        self.assertTrue('id' in str(ex.exception))

        Model2.check_id(None)  # Should just work

        with self.assertRaises(TypeError) as ex:
            Model2.check_id(0)
        self.assertTrue('id' in str(ex.exception))

    def test_to_dict(self):
        """ Test to_dict. """
        self.assertEqual({'id': 1, 'name': 'test'}, Model1.deserialize({'id': 1, 'name': 'test'}).to_dict())
        self.assertEqual({'name': 'hello world'}, Model2.deserialize({'name': 'hello world'}).to_dict())
        self.assertEqual({'name': 'a', 'status': [1, 2]}, Model6.deserialize({'name': 'a', 'status': [1, 2]}).to_dict())
        self.assertEqual({'id': 2, 'name': 'a', 'link': 4, 'room': 5}, Model7.deserialize({'id': 2, 'name': 'a', 'link': 4, 'room': 5}).to_dict())

    def test_from_dict(self):
        """ Test from_dict. """
        model1 = Model1.from_dict({'id': 1, 'name': u'test'})
        self.assertEqual(1, model1.id)
        self.assertEqual('test', model1.name)

        model2 = Model2.from_dict({'name': 'test'})
        self.assertEqual('test', model2.name)

        model6 = Model6.from_dict({'name': u'test', 'status': [1, 2]})
        self.assertEqual('test', model6.name)
        self.assertEqual([1, 2], model6.status)

        model7 = Model7.from_dict({'id': 2, 'name': u'test', 'link': 3, 'room': 5})
        self.assertEqual(2, model7.id)
        self.assertEqual('test', model7.name)
        self.assertEqual(3, model7.link)
        self.assertEqual(5, model7.room)

    def test_from_dict_error(self):
        """ Test from_dict when the dict does not contain the right keys. """
        with self.assertRaises(TypeError):
            Model1.from_dict({'id': 1, 'junk': 'test'})

        with self.assertRaises(TypeError):
            Model1.from_dict({'name': 'test'})

    def test_get_eeprom_data(self):
        """ Test get_eeprom_data. """
        model1 = Model1.deserialize({'id': 1, 'name': u'test'})
        data = model1.get_eeprom_data()

        self.assertEqual(1, len(data))
        self.assertEqual(1, data[0].address.bank)
        self.assertEqual(3, data[0].address.offset)
        self.assertEqual(100, data[0].address.length)
        self.assertEqual(bytearray(b'test') + bytearray([255] * 96), data[0].bytes)

        model2 = Model2.deserialize({'name': 'test'})
        data = model2.get_eeprom_data()

        self.assertEqual(1, len(data))
        self.assertEqual(3, data[0].address.bank)
        self.assertEqual(4, data[0].address.offset)
        self.assertEqual(100, data[0].address.length)
        self.assertEqual(bytearray(b'test') + bytearray([255] * 96), data[0].bytes)

        model3 = Model3.deserialize({'name': 'test', 'link': 123, 'out': 456})
        data = model3.get_eeprom_data()

        self.assertEqual(3, len(data))

        self.assertEqual(3, data[0].address.bank)
        self.assertEqual(14, data[0].address.offset)
        self.assertEqual(1, data[0].address.length)
        self.assertEqual(bytearray([123]), data[0].bytes)

        self.assertEqual(3, data[1].address.bank)
        self.assertEqual(4, data[1].address.offset)
        self.assertEqual(10, data[1].address.length)
        self.assertEqual(bytearray(b'test') + bytearray([255] * 6), data[1].bytes)

        self.assertEqual(3, data[2].address.bank)
        self.assertEqual(15, data[2].address.offset)
        self.assertEqual(2, data[2].address.length)
        self.assertEqual(bytearray([200, 1]), data[2].bytes)

        model6 = Model6.deserialize({'name': u'test', 'status': [1, 2]})
        data = model6.get_eeprom_data()

        self.assertEqual(3, len(data))
        for item in data:
            if item.address.offset == 4:
                self.assertEqual(3, item.address.bank)
                self.assertEqual(10, item.address.length)
                self.assertEqual(bytearray(b'test') + bytearray([255] * 6), item.bytes)
            elif item.address.offset == 14:
                self.assertEqual(3, item.address.bank)
                self.assertEqual(1, item.address.length)
                self.assertEqual(bytearray([1]), item.bytes)
            elif item.address.offset == 15:
                self.assertEqual(3, item.address.bank)
                self.assertEqual(2, item.address.length)
                self.assertEqual(bytearray([2, 0]), item.bytes)
            else:
                self.assertFalse(True)

    def test_get_eeprom_data_readonly(self):
        """ Test get_eeprom_data with a read only field. """
        class RoModel(EepromModel):
            """ Dummy model. """
            id = EepromId(10)
            name = EepromString(100, lambda id: (1, 2 + id))
            other = EepromByte(lambda id: (2, 2 + id), read_only=True)

        model = RoModel.deserialize({'id': 1, 'name': u'test', 'other': 4})
        data = model.get_eeprom_data()

        self.assertEqual(1, len(data))
        self.assertEqual(1, data[0].address.bank)
        self.assertEqual(3, data[0].address.offset)
        self.assertEqual(100, data[0].address.length)
        self.assertEqual(bytearray(b'test') + bytearray([255] * 96), data[0].bytes)


class CompositeDataTypeTest(unittest.TestCase):
    """ Tests for CompositeDataType. """

    def test_get_addresses(self):
        """ Test get_addresses. """
        cdt = CompositeDataType([('one', EepromByte((1, 2))), ('two', EepromByte((1, 3)))])
        addresses = cdt.get_addresses(None, 'cdt')

        self.assertEqual(2, len(addresses))

        self.assertEqual(1, addresses['one'].bank)
        self.assertEqual(2, addresses['one'].offset)
        self.assertEqual(1, addresses['one'].length)

        self.assertEqual(1, addresses['two'].bank)
        self.assertEqual(3, addresses['two'].offset)
        self.assertEqual(1, addresses['two'].length)

    def test_get_addresses_id(self):
        """ Test get_addresses with an id. """
        cdt = CompositeDataType([('one', EepromByte(lambda id: (1, 10+id))),
                                 ('two', EepromByte(lambda id: (1, 20+id)))])
        addresses = cdt.get_addresses(5, 'cdt')

        self.assertEqual(2, len(addresses))

        self.assertEqual(1, addresses['one'].bank)
        self.assertEqual(15, addresses['one'].offset)
        self.assertEqual(1, addresses['one'].length)

        self.assertEqual(1, addresses['two'].bank)
        self.assertEqual(25, addresses['two'].offset)
        self.assertEqual(1, addresses['two'].length)

    def test_get_name(self):
        """ Test get_name. """
        cdt = CompositeDataType([('one', EepromByte((1, 2))), ('two', EepromByte((1, 3)))])
        self.assertEqual('[one(Byte),two(Byte)]', cdt.get_name())


class EepromActionsTest(unittest.TestCase):
    """ Tests for EepromActions. """

    def test_from_bytes(self):
        """ Test from_bytes. """
        actions = EepromActions(1, (0, 0))
        self.assertEqual('1,2', actions.decode(bytearray([1, 2])))

        actions = EepromActions(2, (0, 0))
        self.assertEqual('1,2', actions.decode(bytearray([1, 2, 255, 255])))

    def test_to_bytes(self):
        """ Test to_bytes. """
        actions = EepromActions(1, (0, 0))
        self.assertEqual(bytearray([1, 2]), actions.encode('1,2'))

        actions = EepromActions(2, (0, 0))
        self.assertEqual(bytearray([1, 2, 255, 255]), actions.encode('1,2'))


class EepromSignedTempTest(unittest.TestCase):
    """ Tests for EepromSignedTemp. """

    def test_from_bytes(self):
        """ Test from_bytes. """
        temp = EepromSignedTemp((0, 0))
        self.assertEqual(0.0, temp.decode(bytearray([255])))
        self.assertEqual(1.0, temp.decode(bytearray([0x02])))
        self.assertEqual(-1.0, temp.decode(bytearray([0x82])))
        self.assertEqual(7.5, temp.decode(bytearray([0x0f])))
        self.assertEqual(-7.5, temp.decode(bytearray([0x8f])))

    def test_to_bytes(self):
        """ Test to_bytes. """
        temp = EepromSignedTemp((0, 0))
        self.assertEqual(bytearray([255]), temp.encode(0.0))
        self.assertEqual(bytearray([0x02]), temp.encode(1.0))
        self.assertEqual(bytearray([0x82]), temp.encode(-1.0))
        self.assertEqual(bytearray([0x0f]), temp.encode(7.5))
        self.assertEqual(bytearray([0x8f]), temp.encode(-7.5))

    def test_to_bytes_out_of_range(self):
        """ Test to_bytes with out of range values. """
        temp = EepromSignedTemp((0, 0))

        with self.assertRaises(ValueError):
            temp.encode(8)
        with self.assertRaises(ValueError):
            temp.encode(45)
        with self.assertRaises(ValueError):
            temp.encode(-8)
        with self.assertRaises(ValueError):
            temp.encode(-89)


class EepromIBoolTest(unittest.TestCase):
    """ Tests for EepromIBool. """

    def test_from_bytes(self):
        """ Test from_bytes. """
        temp = EepromIBool((0, 0))
        self.assertEqual(False, temp.decode(bytearray([255])))
        self.assertEqual(True, temp.decode(bytearray([0])))
        self.assertEqual(True, temp.decode(bytearray([15])))

    def test_to_bytes(self):
        """ Test to_bytes. """
        temp = EepromIBool((0, 0))
        self.assertEqual(bytearray([0]), temp.encode(True))
        self.assertEqual(bytearray([255]), temp.encode(False))
