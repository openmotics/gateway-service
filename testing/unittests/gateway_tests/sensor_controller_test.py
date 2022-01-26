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
from __future__ import absolute_import

import unittest

import mock
from peewee import SqliteDatabase

from bus.om_bus_client import MessageClient
from gateway.dto import MasterSensorDTO, SensorDTO, SensorSourceDTO, \
    SensorStatusDTO
from gateway.events import GatewayEvent
from gateway.hal.master_controller import MasterController
from gateway.hal.master_event import MasterEvent
from gateway.maintenance_controller import MaintenanceController
from gateway.models import Plugin, Room, Sensor
from gateway.pubsub import PubSub
from gateway.sensor_controller import SensorController
from ioc import SetTestMode, SetUpTestInjections

MODELS = [Sensor, Room, Plugin]


class SensorControllerTest(unittest.TestCase):
    test_db = None  # type: SqliteDatabase

    @classmethod
    def setUpClass(cls):
        SetTestMode()
        cls.test_db = SqliteDatabase(':memory:')

    def setUp(self):
        self.test_db.bind(MODELS, bind_refs=False, bind_backrefs=False)
        self.test_db.connect()
        self.test_db.create_tables(MODELS)
        self.master_controller = mock.Mock(MasterController)
        self.pubsub = PubSub()
        SetUpTestInjections(maintenance_controller=mock.Mock(MaintenanceController),
                            master_controller=self.master_controller,
                            message_client=mock.Mock(MessageClient),
                            pubsub=self.pubsub)
        self.controller = SensorController()

    def tearDown(self):
        self.test_db.drop_tables(MODELS)
        self.test_db.close()

    def test_master_event(self):
        events = []

        def handle_event(gateway_event):
            events.append(gateway_event)
        self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.STATE, handle_event)

        Sensor.create(id=42, source='master', external_id='1', name='')  # unused

        master_sensors = [MasterSensorDTO(id=0, name='foo'),
                          MasterSensorDTO(id=1, name='bar'),
                          MasterSensorDTO(id=2, name='baz')]
        with mock.patch.object(self.master_controller, 'load_sensors', return_value=master_sensors), \
             mock.patch.object(self.master_controller, 'get_sensors_brightness', return_value=[None]), \
             mock.patch.object(self.master_controller, 'get_sensors_humidity', return_value=[None]), \
             mock.patch.object(self.master_controller, 'get_sensors_temperature', return_value=[None, 21.0, None]):
            self.controller.run_sync_orm()
            self.pubsub._publish_all_events(blocking=False)
        assert GatewayEvent('SENSOR_CHANGE', {'id': 42, 'value': 21.0}) in events
        assert len(events) == 2
        events.pop()

        master_event = MasterEvent(MasterEvent.Types.SENSOR_VALUE, {'sensor': 1, 'type': 'TEMPERATURE', 'value': 22.5})
        self.pubsub.publish_master_event(PubSub.MasterTopics.SENSOR, master_event)
        self.pubsub._publish_all_events(blocking=False)

        assert GatewayEvent('SENSOR_CHANGE', {'id': 42, 'value': 22.5}) in events
        assert len(events) == 2
        events.pop()

        master_event = MasterEvent(MasterEvent.Types.SENSOR_VALUE, {'sensor': 1, 'type': 'TEMPERATURE', 'value': None})
        self.pubsub.publish_master_event(PubSub.MasterTopics.SENSOR, master_event)
        self.pubsub._publish_all_events(blocking=False)

        assert GatewayEvent('SENSOR_CHANGE', {'id': 42, 'value': None}) in events
        assert len(events) == 2

    def test_sync(self):
        events = []

        def handle_event(gateway_event):
            events.append(gateway_event)
        self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.CONFIG, handle_event)

        Sensor.create(id=42, source='master', external_id='1', name='')  # unused
        Sensor.create(id=43, source='master', external_id='8', name='')  # removed

        master_sensors = [MasterSensorDTO(id=0, name='foo'),
                          MasterSensorDTO(id=1, name='bar'),
                          MasterSensorDTO(id=2, name='baz')]
        with mock.patch.object(self.master_controller, 'load_sensors', return_value=master_sensors), \
             mock.patch.object(self.master_controller, 'get_sensors_brightness', return_value=[84.0, None, None]), \
             mock.patch.object(self.master_controller, 'get_sensors_humidity', return_value=[None, None, 49.0]), \
             mock.patch.object(self.master_controller, 'get_sensors_temperature', return_value=[21.0, None, None]):
            self.controller.run_sync_orm()
            self.pubsub._publish_all_events(blocking=False)
        assert GatewayEvent('CONFIG_CHANGE', {'type': 'sensor'}) in events
        assert len(events) == 1

        assert Sensor.select().where(Sensor.physical_quantity == 'brightness').count() == 1
        sensor = Sensor.get(Sensor.physical_quantity == 'brightness')
        assert sensor.external_id == '0'
        assert sensor.source == 'master'
        assert sensor.name == 'foo'
        assert Sensor.select().where(Sensor.physical_quantity == 'humidity').count() == 1
        sensor = Sensor.get(Sensor.physical_quantity == 'humidity')
        assert sensor.external_id == '2'
        assert sensor.source == 'master'
        assert sensor.name == 'baz'
        assert Sensor.select().where(Sensor.physical_quantity == 'temperature').count() == 1
        sensor = Sensor.get(Sensor.physical_quantity == 'temperature')
        assert sensor.external_id == '0'
        assert sensor.source == 'master'
        assert sensor.name == 'foo'
        assert Sensor.select().where(Sensor.physical_quantity.is_null()).count() == 1
        assert Sensor.select().count() == 4

    def test_sync_migrate_existing(self):
        events = []

        def handle_event(gateway_event):
            events.append(gateway_event)
        self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.CONFIG, handle_event)

        room = Room.create(number=2, name='Livingroom')
        Sensor.create(source='master', external_id='1', name='', room=room)

        master_sensors = [MasterSensorDTO(id=0, name='foo'),
                          MasterSensorDTO(id=1, name='bar')]
        with mock.patch.object(self.master_controller, 'load_sensors', return_value=master_sensors), \
             mock.patch.object(self.master_controller, 'get_sensors_brightness', return_value=[None, None]), \
             mock.patch.object(self.master_controller, 'get_sensors_humidity', return_value=[None, 49.0]), \
             mock.patch.object(self.master_controller, 'get_sensors_temperature', return_value=[None, 21.0]):
            self.controller.run_sync_orm()
            self.pubsub._publish_all_events(blocking=False)
        assert GatewayEvent('CONFIG_CHANGE', {'type': 'sensor'}) in events
        assert len(events) == 1

        assert Sensor.select().where(Sensor.physical_quantity == 'humidity').count() == 1
        sensor = Sensor.get(Sensor.physical_quantity == 'humidity')
        assert sensor.external_id == '1'
        assert sensor.source == 'master'
        assert sensor.name == 'bar'
        assert sensor.room == room
        assert Sensor.select().where(Sensor.physical_quantity == 'temperature').count() == 1
        sensor = Sensor.get(Sensor.physical_quantity == 'temperature')
        assert sensor.external_id == '1'
        assert sensor.source == 'master'
        assert sensor.name == 'bar'
        assert sensor.room == room
        assert Sensor.select().where(Sensor.physical_quantity == 'brightness').count() == 0
        assert Sensor.select().count() == 2

    def test_sync_max_id(self):
        Sensor.create(id=239, source='master', external_id='2', name='')  # id out of range

        master_sensors = [MasterSensorDTO(id=0, name='foo'),
                          MasterSensorDTO(id=1, name='bar'),
                          MasterSensorDTO(id=2, name='baz')]
        with mock.patch.object(self.master_controller, 'load_sensors', return_value=master_sensors), \
             mock.patch.object(self.master_controller, 'get_sensors_brightness', return_value=[84.0, None, None]), \
             mock.patch.object(self.master_controller, 'get_sensors_humidity', return_value=[None, None, 49.0]), \
             mock.patch.object(self.master_controller, 'get_sensors_temperature', return_value=[21.0, None, None]):
            self.controller.run_sync_orm()
            self.controller.run_sync_orm()  # recover after failed sync
            self.pubsub._publish_all_events(blocking=False)

        assert Sensor.select().count() == 3
        sensor_ids = list(i for (i,) in Sensor.select(Sensor.id).tuples())
        assert all(i < 200 for i in sensor_ids), sensor_ids

    def test_load_sensor(self):
        Sensor.create(id=42, source='master', external_id='0', physical_quantity='temperature', unit='celcius', name='foo')
        master_sensor_dto = SensorDTO(id=0, name='bar')
        with mock.patch.object(self.master_controller, 'load_sensor', return_value=master_sensor_dto) as load, \
             mock.patch.object(self.master_controller, 'load_sensors', return_value=[]):
            sensor_dto = self.controller.load_sensor(42)
        assert sensor_dto.id == 42
        assert sensor_dto.source == SensorSourceDTO('master')
        assert sensor_dto.external_id == '0'
        assert sensor_dto.physical_quantity == 'temperature'
        assert sensor_dto.name == 'foo'
        load.assert_called_with(sensor_id=0)

    def test_load_sensors(self):
        Sensor.create(id=42, source='master', external_id='0', physical_quantity='temperature', unit='celcius', name='foo')
        Sensor.create(id=43, source='master', external_id='0', physical_quantity=None, unit=None, name='')
        master_sensor_dto = SensorDTO(id=0, name='bar')
        with mock.patch.object(self.master_controller, 'load_sensor', return_value=master_sensor_dto) as load, \
             mock.patch.object(self.master_controller, 'load_sensors', return_value=[]):
            sensor_dtos = self.controller.load_sensors()
        assert len(sensor_dtos) == 1
        sensor_dto = sensor_dtos[0]
        assert sensor_dto.id == 42
        assert sensor_dto.source == SensorSourceDTO('master')
        assert sensor_dto.external_id == '0'
        assert sensor_dto.physical_quantity == 'temperature'
        assert sensor_dto.name == 'foo'
        load.assert_called_with(sensor_id=0)

    def test_save_sensors(self):
        events = []

        def handle_event(gateway_event):
            events.append(gateway_event)
        self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.CONFIG, handle_event)

        sensor_id = 42
        room = Room.create(number=2, name='Livingroom')
        Sensor.create(id=sensor_id, source='master', external_id='0', name='')
        sensor_dto = SensorDTO(id=sensor_id, physical_quantity='temperature', unit='celcius', name='foo', room=2)
        with mock.patch.object(self.master_controller, 'save_sensors') as save:
            saved_sensors = self.controller.save_sensors([sensor_dto])
            self.pubsub._publish_all_events(blocking=False)
            save.assert_called_with([MasterSensorDTO(id=0, name='foo')])
            assert sensor_id in [saved_sensor.id for saved_sensor in saved_sensors]

        assert GatewayEvent('CONFIG_CHANGE', {'type': 'sensor'}) in events
        assert len(events) == 1

        sensor = Sensor.select().where(Sensor.id == 42).get()
        assert sensor.physical_quantity == 'temperature'
        assert sensor.name == 'foo'
        assert sensor.room == room
        master_sensor_dtos = save.call_args_list[0][0][0]
        assert [0] == [x.id for x in master_sensor_dtos]
        assert ['foo'] == [x.name for x in master_sensor_dtos]

    def test_save_sensors_create(self):
        events = []

        def handle_event(gateway_event):
            events.append(gateway_event)
        self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.CONFIG, handle_event)

        plugin = Plugin.create(id=10, name='dummy', version='0.0.1')
        sensor_dto = SensorDTO(id=None,
                               source=SensorSourceDTO('plugin', name='dummy'),
                               external_id='foo',
                               physical_quantity='temperature',
                               unit='celcius',
                               name='foo')
        with mock.patch.object(self.master_controller, 'save_sensors') as save:
            saved_sensors = self.controller.save_sensors([sensor_dto])
            self.pubsub._publish_all_events(blocking=False)
            save.assert_not_called()
            assert all([saved_sensor.id for saved_sensor in saved_sensors])

        assert GatewayEvent('CONFIG_CHANGE', {'type': 'sensor'}) in events
        assert len(events) == 1

        sensor = Sensor.select().where(Sensor.physical_quantity == 'temperature').get()
        assert sensor.id > 500
        assert sensor.source == 'plugin'
        assert sensor.plugin.id == plugin.id
        assert sensor.external_id == 'foo'
        assert sensor.unit == 'celcius'
        assert sensor.name == 'foo'

    def test_save_sensors_update(self):
        events = []

        def handle_event(gateway_event):
            events.append(gateway_event)
        self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.CONFIG, handle_event)

        plugin = Plugin.create(id=10, name='dummy', version='0.0.1')
        Sensor.create(id=512, plugin=plugin, source='plugin', external_id='foo', physical_quantity='temperature', name='')
        sensor_dto = SensorDTO(id=None,
                               source=SensorSourceDTO('plugin', name='dummy'),
                               external_id='foo',
                               physical_quantity='temperature',
                               unit='celcius',
                               name='foo')
        with mock.patch.object(self.master_controller, 'save_sensors') as save:
            saved_sensors = self.controller.save_sensors([sensor_dto])
            self.pubsub._publish_all_events(blocking=False)
            save.assert_not_called()
            assert all([saved_sensor.id for saved_sensor in saved_sensors])

        assert GatewayEvent('CONFIG_CHANGE', {'type': 'sensor'}) in events
        assert len(events) == 1

        sensor = Sensor.select().where(Sensor.physical_quantity == 'temperature').get()
        assert sensor.id > 500
        assert sensor.source == 'plugin'
        assert sensor.plugin.id == plugin.id
        assert sensor.external_id == 'foo'
        assert sensor.unit == 'celcius'
        assert sensor.name == 'foo'

    def test_save_sensors_master_virtual(self):
        events = []

        def handle_event(gateway_event):
            events.append(gateway_event)
        self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.CONFIG, handle_event)

        sensor_dto = SensorDTO(id=None,
                               source=SensorSourceDTO('master'),
                               external_id='31',
                               physical_quantity='temperature',
                               unit='celcius',
                               name='foo',
                               offset=-1.0,
                               virtual=True)
        with mock.patch.object(self.master_controller, 'save_sensors') as save:
            saved_sensors = self.controller.save_sensors([sensor_dto])
            self.pubsub._publish_all_events(blocking=False)
            save.assert_called_with([MasterSensorDTO(id=31, name='foo', virtual=True, offset=-1.0)])
            assert all([saved_sensor.id is not None for saved_sensor in saved_sensors])

        assert GatewayEvent('CONFIG_CHANGE', {'type': 'sensor'}) in events
        assert len(events) == 1

        sensor = Sensor.select().where(Sensor.physical_quantity == 'temperature').get()
        assert sensor.id < 200
        assert sensor.source == 'master'
        assert sensor.external_id == '31'
        assert sensor.unit == 'celcius'
        assert sensor.name == 'foo'

    def test_status_sync(self):
        events = []

        def handle_event(gateway_event):
            events.append(gateway_event)
        self.pubsub.subscribe_gateway_events(PubSub.GatewayTopics.STATE, handle_event)

        master_sensors = [MasterSensorDTO(id=0, name='foo'),
                          MasterSensorDTO(id=1, name='bar'),
                          MasterSensorDTO(id=2, name='baz')]
        with mock.patch.object(self.master_controller, 'load_sensors', return_value=master_sensors), \
             mock.patch.object(self.master_controller, 'get_sensors_brightness', return_value=[84.0, None, None]), \
             mock.patch.object(self.master_controller, 'get_sensors_humidity', return_value=[None, None, 49.0]), \
             mock.patch.object(self.master_controller, 'get_sensors_temperature', return_value=[21.0, None, None]):
            self.controller.run_sync_orm()
            self.pubsub._publish_all_events(blocking=False)
            values = {s.id: s for s in self.controller.get_sensors_status()}

        assert Sensor.select().count() == 3
        sensor = Sensor.get(Sensor.physical_quantity == 'brightness')
        assert values[sensor.id].value == 84.0
        assert GatewayEvent('SENSOR_CHANGE', {'id': sensor.id, 'value': 84.0}) in events
        sensor = Sensor.get(Sensor.physical_quantity == 'humidity')
        assert values[sensor.id].value == 49.0
        assert GatewayEvent('SENSOR_CHANGE', {'id': sensor.id, 'value': 49.0}) in events
        sensor = Sensor.get(Sensor.physical_quantity == 'temperature')
        assert values[sensor.id].value == 21.0
        assert GatewayEvent('SENSOR_CHANGE', {'id': sensor.id, 'value': 21.0}) in events
        assert len(events) == 6

    def test_set_sensor_status(self):
        sensor = Sensor.create(id=512, source='plugin', external_id='0', physical_quantity='brightness', name='')
        with mock.patch.object(self.master_controller, 'load_sensors', return_value=[]), \
             mock.patch.object(self.master_controller, 'get_sensors_brightness', return_value=[]), \
             mock.patch.object(self.master_controller, 'get_sensors_humidity', return_value=[]), \
             mock.patch.object(self.master_controller, 'get_sensors_temperature', return_value=[]):
            self.controller.set_sensor_status(SensorStatusDTO(sensor.id, value=21))
            values = {s.id: s for s in self.controller.get_sensors_status()}
        assert values[sensor.id].value == 21.0

    def test_get_brightness_status(self):
        sensor = Sensor.create(id=0, source='master', external_id='0', physical_quantity='brightness', name='')
        master_sensors = [MasterSensorDTO(id=0, name='foo'),
                          MasterSensorDTO(id=1, name='bar'),
                          MasterSensorDTO(id=2, name='baz')]
        with mock.patch.object(self.master_controller, 'load_sensors', return_value=master_sensors), \
             mock.patch.object(self.master_controller, 'get_sensors_brightness', return_value=[84.0, None, None]), \
             mock.patch.object(self.master_controller, 'get_sensors_humidity', return_value=[None, None, None]), \
             mock.patch.object(self.master_controller, 'get_sensors_temperature', return_value=[None, None, None]):
            self.controller.run_sync_orm()
            values = self.controller.get_brightness_status()
        assert values[sensor.id] == 84.0
        assert values == [84.0]

    def test_get_humidity_status(self):
        sensor = Sensor.create(id=5, source='master', external_id='2', physical_quantity='humidity', name='')
        master_sensors = [MasterSensorDTO(id=0, name='foo'),
                          MasterSensorDTO(id=1, name='bar'),
                          MasterSensorDTO(id=2, name='baz')]
        with mock.patch.object(self.master_controller, 'load_sensors', return_value=master_sensors), \
             mock.patch.object(self.master_controller, 'get_sensors_brightness', return_value=[None, None, None]), \
             mock.patch.object(self.master_controller, 'get_sensors_humidity', return_value=[None, None, 49.0]), \
             mock.patch.object(self.master_controller, 'get_sensors_temperature', return_value=[None, None, None]):
            self.controller.run_sync_orm()
            values = self.controller.get_humidity_status()
        assert values[sensor.id] == 49.0
        assert values == [None, None, None, None, None, 49.0]

    def test_get_temperature_status(self):
        Sensor.create(id=0, source='master', external_id='1', name='')
        sensor = Sensor.create(id=2, source='master', external_id='0', physical_quantity='temperature', name='')
        master_sensors = [MasterSensorDTO(id=0, name='foo'),
                          MasterSensorDTO(id=1, name='bar'),
                          MasterSensorDTO(id=2, name='baz')]
        with mock.patch.object(self.master_controller, 'load_sensors', return_value=master_sensors), \
             mock.patch.object(self.master_controller, 'get_sensors_brightness', return_value=[84.0, None, None]), \
             mock.patch.object(self.master_controller, 'get_sensors_humidity', return_value=[None, None, 49.0]), \
             mock.patch.object(self.master_controller, 'get_sensors_temperature', return_value=[21.0, 20.5, None]):
            self.controller.run_sync_orm()
            values = self.controller.get_temperature_status()
        assert values[sensor.id] == 21.0
        assert values == [20.5, None, 21.0]
