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

from __future__ import absolute_import

import json
import logging
import time

from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, \
    Text, UniqueConstraint, and_, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import RelationshipProperty, relationship, \
    scoped_session, sessionmaker
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.schema import MetaData
# from sqlalchemy_utils import ChoiceType
from sqlite3 import Connection as SQLite3Connection
from sqlalchemy import event

import constants


# explicitly activate foreign key constraints
def _set_fk_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, SQLite3Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()


_ = and_, NoResultFound  # For easier import

if False:  # MYPY
    from typing import Any, Dict, List, Optional, TypeVar
    from sqlalchemy.orm import RelationshipProperty
    T = TypeVar('T')

logger = logging.getLogger(__name__)

SQLALCHEMY_DATABASE_URL = "sqlite:///{}".format(constants.get_gateway_database_file())
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
# bind the foreign key pragma listener explicitly to this engine, making sure not to use a global listener with a
# decorator as then the alembic migration will apply it too, resulting in data loss after migration
event.listen(engine, 'connect', _set_fk_pragma)
session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Session = scoped_session(session_factory)


class Database:
    @staticmethod
    def get_session():
        return Session()


# https://alembic.sqlalchemy.org/en/latest/naming.html
convention = {
  "ix": "ix_%(column_0_label)s",
  "uq": "uq_%(table_name)s_%(column_0_name)s",
  "ck": "ck_%(table_name)s_%(constraint_name)s",
  "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
  "pk": "pk_%(table_name)s"
}

Base = declarative_base(metadata=MetaData(naming_convention=convention))


class Feature(Base):
    __tablename__ = 'feature'
    __table_args__ = {'sqlite_autoincrement': True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)
    enabled = Column(Boolean, nullable=False)

    THERMOSTATS_GATEWAY = 'thermostats_gateway'


class MasterNumber(object):
    number = Column(Integer, unique=True, nullable=False)

    def __init__(self, number=None):
        # type: (int) -> None
        pass


class Input(Base, MasterNumber):
    __tablename__ = 'input'
    __table_args__ = {'sqlite_autoincrement': True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_enabled = Column(Boolean, default=False, nullable=False)
    room_id = Column(Integer, ForeignKey('room.id', ondelete='SET NULL'), nullable=True)
    name = Column(String(255), default='', nullable=False)
    in_use = Column(Boolean, nullable=False, default=True)

    room = relationship('Room', innerjoin=False)  # type: RelationshipProperty[Optional[Room]]


class Output(Base, MasterNumber):
    __tablename__ = 'output'
    __table_args__ = {'sqlite_autoincrement': True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(Integer, ForeignKey('room.id', ondelete='SET NULL'), nullable=True)
    name = Column(String(255), default='', nullable=False)
    in_use = Column(Boolean, nullable=False, default=True)

    room = relationship('Room', lazy='joined', innerjoin=False)  # type: RelationshipProperty[Optional[Room]]
    pump = relationship('Pump', back_populates='output', uselist=False)  # type: RelationshipProperty[Optional[Pump]]
    valve = relationship('Valve', back_populates='output', uselist=False)  # type: RelationshipProperty[Optional[Valve]]


class Sensor(Base):
    __tablename__ = 'sensor'
    __table_args__ = (UniqueConstraint('source', 'plugin_id', 'external_id', 'physical_quantity'), {'sqlite_autoincrement': True})

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(255), nullable=False)
    external_id = Column(String(255), nullable=False)
    physical_quantity = Column(String(255), nullable=True)
    unit = Column(String(255), nullable=True)
    name = Column(String(255), nullable=False)
    room_id = Column(Integer, ForeignKey('room.id', ondelete='SET NULL'), nullable=True)
    plugin_id = Column(Integer, ForeignKey('plugin.id', ondelete='CASCADE'), nullable=True)
    in_use = Column(Boolean, nullable=False, default=True)

    room = relationship('Room', lazy='joined', innerjoin=False)  # type: RelationshipProperty[Optional[Room]]
    plugin = relationship('Plugin', lazy='joined', innerjoin=False)  # type: RelationshipProperty[Optional[Plugin]]

    class Sources(object):
        MASTER = 'master'
        PLUGIN = 'plugin'

    class PhysicalQuantities:
        TEMPERATURE = 'temperature'
        HUMIDITY = 'humidity'
        BRIGHTNESS = 'brightness'
        SOUND = 'sound'
        DUST = 'dust'
        COMFORT_INDEX = 'comfort_index'
        AQI = 'aqi'
        CO2 = 'co2'
        VOC = 'voc'

    class Units:
        NONE = 'none'
        CELCIUS = 'celcius'
        PERCENT = 'percent'
        DECIBEL = 'decibel'
        LUX = 'lux'
        MICRO_GRAM_PER_CUBIC_METER = 'micro_gram_per_cubic_meter'
        PARTS_PER_MILLION = 'parts_per_million'


class Shutter(Base, MasterNumber):
    __tablename__ = 'shutter'
    __table_args__ = {'sqlite_autoincrement': True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(Integer, ForeignKey('room.id', ondelete='SET NULL'), nullable=True)
    name = Column(String(255), default='', nullable=False)
    in_use = Column(Boolean, nullable=False, default=True)

    room = relationship('Room', lazy='joined', innerjoin=False)  # type: RelationshipProperty[Optional[Room]]


class ShutterGroup(Base, MasterNumber):
    __tablename__ = 'shuttergroup'
    __table_args__ = {'sqlite_autoincrement': True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(Integer, ForeignKey('room.id', ondelete='SET NULL'), nullable=True)
    in_use = Column(Boolean, nullable=False, default=True)

    room = relationship('Room', lazy='joined', innerjoin=False)  # type: RelationshipProperty[Optional[Room]]


class PulseCounter(Base, MasterNumber):
    __tablename__ = 'pulsecounter'
    __table_args__ = {'sqlite_autoincrement': True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    source = Column(String(255), nullable=False)  # Options: 'master' or 'gateway'
    persistent = Column(Boolean, nullable=False)
    room_id = Column(Integer, ForeignKey('room.id', ondelete='SET NULL'), nullable=True)
    in_use = Column(Boolean, nullable=False, default=True)

    room = relationship('Room', lazy='joined', innerjoin=False)  # type: RelationshipProperty[Optional[Room]]


class GroupAction(Base, MasterNumber):
    __tablename__ = 'groupaction'
    __table_args__ = {'sqlite_autoincrement': True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    show_in_app = Column(Boolean, nullable=False, default=True)
    name = Column(String(255), default='', nullable=False)


class Module(Base):
    __tablename__ = 'module'
    __table_args__ = {'sqlite_autoincrement': True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(255), nullable=False)
    address = Column(String(255), nullable=False)
    module_type = Column(String(255), nullable=True)
    hardware_type = Column(String(255), nullable=False)
    firmware_version = Column(String(255), nullable=True)
    hardware_version = Column(String(255), nullable=True)
    order = Column(Integer, nullable=True)
    last_online_update = Column(Integer, nullable=True)
    update_success = Column(Boolean, nullable=True)


class EnergyModule(Base, MasterNumber):
    __tablename__ = 'energymodule'
    __table_args__ = {'sqlite_autoincrement': True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(Integer, nullable=False)
    name = Column(String(255), default='', nullable=False)
    module_id = Column(Integer, ForeignKey('module.id', ondelete="CASCADE"), unique=True, nullable=False)

    module = relationship('Module', foreign_keys=[module_id])
    cts = relationship("EnergyCT",  lazy='joined', innerjoin=False, back_populates="energy_module")  # type: RelationshipProperty[List[EnergyCT]]


class EnergyCT(Base):
    __tablename__ = 'energyct'
    __table_args__ = (UniqueConstraint('number', 'energy_module_id'), {'sqlite_autoincrement': True})

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), default='', nullable=False)
    number = Column(Integer, unique=False, nullable=False)
    sensor_type = Column(Integer, nullable=False)
    times = Column(String(255), nullable=False)
    inverted = Column(Boolean, default=False, nullable=False)
    energy_module_id = Column(Integer, ForeignKey('energymodule.id', ondelete="CASCADE"), nullable=False)
    energy_module = relationship("EnergyModule",  lazy='joined', innerjoin=False, back_populates="cts")  # type: RelationshipProperty[Optional[EnergyModule]]


class Schedule(Base):
    __tablename__ = 'schedule'
    __table_args__ = {'sqlite_autoincrement': True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    start = Column(Float, nullable=False)
    repeat = Column(String(255), nullable=True)
    duration = Column(Float, nullable=True)
    end = Column(Float, nullable=True)
    action = Column(String(255), nullable=False)
    arguments = Column(String(255), nullable=True)
    status = Column(String(255), nullable=False)

    class Sources:
        GATEWAY = 'gateway'
        THERMOSTATS = 'thermostats'


class Config(Base):
    __tablename__ = 'config'
    __table_args__ = {'sqlite_autoincrement': True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    setting = Column(String(255), unique=True, nullable=False)
    data = Column(String(255), nullable=False)

    CACHE_EXPIRY_DURATION = 60
    CACHE = {}  # type: Dict[str,Any]

    @staticmethod
    def get_entry(key, fallback):
        # type: (str, T) -> T
        """ Retrieves a setting from the DB, returns the argument 'fallback' when non existing """
        key = key.lower()
        if key in Config.CACHE:
            data, expire_at = Config.CACHE[key]
            if expire_at > time.time():
                return data
        with Database.get_session() as db:
            raw_data = db.query(Config.data).where(Config.setting == key).one_or_none()
        if raw_data is not None:
            data = json.loads(raw_data[0])
        else:
            data = fallback
        Config.CACHE[key] = (data, time.time() + Config.CACHE_EXPIRY_DURATION)
        return data

    @staticmethod
    def set_entry(key, value):
        # type: (str, Any) -> None
        """ Sets a setting in the DB, does overwrite if already existing """
        key = key.lower()
        data = json.dumps(value)
        with Database.get_session() as db:
            config_orm = db.query(Config).where(Config.setting == key).one_or_none()
            if config_orm is not None:
                # if the key already exists, update the value
                config_orm.data = data
            else:
                # create a new setting if it was non existing
                config_orm = Config(setting=key, data=data)
            db.add(config_orm)
            db.commit()
        Config.CACHE[key] = (value, time.time() + Config.CACHE_EXPIRY_DURATION)

    @staticmethod
    def remove_entry(key):
        # type: (str) -> int
        """ Removes a setting from the DB """
        with Database.get_session() as db:
            rows_deleted = db.query(Config).where(Config.setting == key.lower()).delete()
            db.commit()
        Config.CACHE.pop(key, None)
        return rows_deleted


class Plugin(Base):
    __tablename__ = 'plugin'
    __table_args__ = {'sqlite_autoincrement': True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)
    version = Column(String(255), nullable=False)


class Ventilation(Base):
    __tablename__ = 'ventilation'
    __table_args__ = (UniqueConstraint('source', 'plugin_id', 'external_id'), {'sqlite_autoincrement': True})

    class Sources(object):
        PLUGIN = 'plugin'

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(255), nullable=False)  # Options: 'gateway' or 'plugin'
    plugin_id = Column(Integer, ForeignKey('plugin.id', ondelete='CASCADE'), nullable=True)
    external_id = Column(String(255), nullable=False)  # eg. serial number
    name = Column(String(255), nullable=False)
    room_id = Column(Integer, ForeignKey('room.id', ondelete='SET NULL'), nullable=True)
    amount_of_levels = Column(Integer, nullable=False)
    device_vendor = Column(String(255), nullable=True)
    device_type = Column(String(255), nullable=True)
    device_serial = Column(String(255), nullable=True)

    plugin = relationship('Plugin', lazy='joined', innerjoin=False)  # type: RelationshipProperty[Optional[Plugin]]
    room = relationship('Room', lazy='joined', innerjoin=False)  # type: RelationshipProperty[Optional[Room]]


class ThermostatGroup(Base, MasterNumber):
    __tablename__ = 'thermostatgroup'
    __table_args__ = {'sqlite_autoincrement': True}

    class Modes(object):
        HEATING = 'heating'
        COOLING = 'cooling'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    threshold_temperature = Column(Float, nullable=True, default=None)
    sensor_id = Column(Integer, ForeignKey('sensor.id', ondelete='SET NULL'), nullable=True)
    mode = Column(String(255), default=Modes.HEATING, nullable=False)  # Options: 'heating' or 'cooling'

    sensor = relationship('Sensor')  # type: RelationshipProperty[Optional[Sensor]]
    thermostats = relationship('Thermostat', back_populates='group')  # type: RelationshipProperty[List[Thermostat]]
    outputs = relationship('Output', secondary='hvac_output_link')  # type: RelationshipProperty[List[Output]]

    heating_output_associations = relationship('HvacOutputLink',
                                               primaryjoin='and_(ThermostatGroup.id == HvacOutputLink.hvac_id, HvacOutputLink.mode == "heating")',
                                               order_by='asc(HvacOutputLink.id)',
                                               back_populates='hvac')  # type: RelationshipProperty[List[HvacOutputLink]]
    cooling_output_associations = relationship('HvacOutputLink',
                                               primaryjoin='and_(ThermostatGroup.id == HvacOutputLink.hvac_id, HvacOutputLink.mode == "cooling")',
                                               order_by='asc(HvacOutputLink.id)',
                                               back_populates='hvac')  # type: RelationshipProperty[List[HvacOutputLink]]




# thermostatsV2
class HvacOutputLink(Base):
    class Modes(object):
        HEATING = 'heating'
        COOLING = 'cooling'
        OFF = 'off'
        

    __tablename__ = "hvac_output_link"
    __table_args__ = (
        UniqueConstraint('hvac_id', 'output_id', 'mode'),
        {'sqlite_autoincrement': True},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    # hvac_id = Column(Integer, ForeignKey('hvac.id', ondelete='CASCADE'), nullable=False)
    hvac_id = Column(Integer, ForeignKey('thermostatgroup.id', ondelete='CASCADE'), nullable=False)  # todo: currently this is the id of thermostat_group_id but setting name for future changes
    output_id = Column(Integer, ForeignKey('output.id', ondelete='CASCADE'), nullable=False)
    mode = Column(String, nullable=False, default='heating')  # The mode this config is used for

    value = Column(Integer, nullable=False, default=100)  # The value that needs to be set on the output when in this mode (0-100)

    output = relationship('Output')
    hvac = relationship('ThermostatGroup')




class PumpToValveAssociation(Base):
    __tablename__ = 'pumptovalve'
    __table_args__ = {'sqlite_autoincrement': True}

    pump_id = Column(Integer, ForeignKey('pump.id', ondelete='CASCADE'), primary_key=True)
    valve_id = Column(Integer, ForeignKey('valve.id', ondelete='CASCADE'), primary_key=True)

    pump = relationship('Pump')
    valve = relationship('Valve')


class Pump(Base):
    __tablename__ = 'pump'
    __table_args__ = {'sqlite_autoincrement': True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    output_id = Column(Integer, ForeignKey('output.id', ondelete='CASCADE'), nullable=True, unique=True)

    output = relationship('Output', lazy='joined', back_populates='pump')

    valves = relationship('Valve', back_populates='pump', secondary='pumptovalve')  # type: RelationshipProperty[List[Valve]]

    # heating_valves = relationship('Valve', back_populates='pump', secondary='pumptovalve',
    #                               secondaryjoin='and_(Valve.id == PumpToValveAssociation.valve_id, Valve.mode == "heating")')
    # cooling_valves = relationship('Valve', back_populates='pump', secondary='pumptovalve',
    #                               secondaryjoin='and_(Valve.id == PumpToValveAssociation.valve_id, Valve.mode == "cooling")')

    # TODO: implement custom filters
    # @property
    # def heating_valves(self):  # type: () -> List[Valve]
    #     return self._valves(mode=ThermostatGroup.Modes.HEATING)
    #
    # @property
    # def cooling_valves(self):  # type: () -> List[Valve]
    #     return self._valves(mode=ThermostatGroup.Modes.COOLING)
    #
    # def _valves(self, mode):  # type: (str) -> List[Valve]
    #     return [valve for valve in Valve.select(Valve, ValveToThermostat.mode, ValveToThermostat.priority)
    #                                     .distinct()
    #                                     .join_from(Valve, ValveToThermostat)
    #                                     .join_from(Valve, PumpToValve)
    #                                     .join_from(PumpToValve, Pump)
    #                                     .where((ValveToThermostat.mode == mode) &
    #                                            (Pump.id == self.id))
    #                                     .order_by(ValveToThermostat.priority)]


class Valve(Base):
    __tablename__ = 'valve'
    __table_args__ = {'sqlite_autoincrement': True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    delay = Column(Integer, default=60, nullable=False)
    output_id = Column(Integer, ForeignKey('output.id', ondelete='CASCADE'), unique=True, nullable=False)

    output = relationship('Output', lazy='joined', back_populates='valve')
    pump = relationship('Pump', secondary='pumptovalve')  # type: RelationshipProperty[Optional[Pump]]
    # thermostat_associations = relationship('IndoorLinkValves', lazy='joined', back_populates='valve')
    thermostat_associations = relationship('IndoorLinkValves', lazy='joined', back_populates='valve')  #type: RelationshipProperty[List[IndoorLinkValves]]


class Thermostat(Base, MasterNumber):
    __tablename__ = 'thermostat'
    __table_args__ = {'sqlite_autoincrement': True}

    class ValveConfigs(object):
        CASCADE = 'cascade'
        EQUAL = 'equal'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), default='Thermostat', nullable=False)
    state = Column(String(255), default='on', nullable=False)
    sensor_id = Column(Integer, ForeignKey('sensor.id', ondelete='SET NULL'), nullable=True)
    pid_heating_p = Column(Float, default=120, nullable=False)
    pid_heating_i = Column(Float, default=0, nullable=False)
    pid_heating_d = Column(Float, default=0, nullable=False)
    pid_cooling_p = Column(Float, default=120, nullable=False)
    pid_cooling_i = Column(Float, default=0, nullable=False)
    pid_cooling_d = Column(Float, default=0, nullable=False)
    automatic = Column(Boolean, default=True, nullable=False)
    room_id = Column(Integer, ForeignKey('room.id', ondelete='SET NULL'), nullable=True)
    start = Column(Integer, nullable=False)
    valve_config = Column(String(255), default=ValveConfigs.CASCADE, nullable=False)  # Options: 'cascade' or 'equal'
    thermostat_group_id = Column(Integer, ForeignKey('thermostatgroup.id', ondelete='CASCADE'), nullable=False)

    room = relationship('Room', lazy='joined', innerjoin=False)  # type: RelationshipProperty[Optional[Room]]
    sensor = relationship('Sensor')
    group = relationship('ThermostatGroup')

    presets = relationship('Preset', back_populates='thermostat')  # type: RelationshipProperty[List[Preset]]
    active_preset = relationship('Preset',
                                 primaryjoin='and_(Thermostat.id == Preset.thermostat_id, Preset.active == True)',
                                 back_populates='thermostat', uselist=False)  # type: RelationshipProperty[Preset]

    valves = relationship('Valve', secondary='indoor_link_valves')  # type: RelationshipProperty[List[Valve]]
    heating_valve_associations = relationship('IndoorLinkValves',
                                              primaryjoin='and_(Thermostat.id == IndoorLinkValves.thermostat_link_id, IndoorLinkValves.mode == "heating")')  # type: RelationshipProperty[List[IndoorLinkValves]]
    cooling_valve_associations = relationship('IndoorLinkValves',
                                              primaryjoin='and_(Thermostat.id == IndoorLinkValves.thermostat_link_id, IndoorLinkValves.mode == "cooling")')  # type: RelationshipProperty[List[IndoorLinkValves]]

    schedules = relationship('DaySchedule', back_populates='thermostat')  # type: RelationshipProperty[List[DaySchedule]]
    heating_schedules = relationship('DaySchedule',
                                     primaryjoin='and_(Thermostat.id == DaySchedule.thermostat_id, DaySchedule.mode == "heating")',
                                     order_by='asc(DaySchedule.index)')  # type: RelationshipProperty[List[DaySchedule]]
    cooling_schedules = relationship('DaySchedule',
                                     primaryjoin='and_(Thermostat.id == DaySchedule.thermostat_id, DaySchedule.mode == "cooling")',
                                     order_by='asc(DaySchedule.index)')  # type: RelationshipProperty[List[DaySchedule]]



class IndoorLinkValves(Base):
    __tablename__ = 'indoor_link_valves'
    __table_args__ = {'sqlite_autoincrement': True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    # thermostat_link_id = Column(Integer, ForeignKey('indoor_thermostat_pid.id', ondelete='CASCADE'), nullable=False)
    thermostat_link_id = Column(Integer, ForeignKey('thermostat.id', ondelete='CASCADE'))  # currently linked directly to the thermostat, in thermostat V2 it will be linked to indoor controller (pid controller)
    valve_id = Column(Integer, ForeignKey('valve.id', ondelete='CASCADE'), nullable=False)
    mode = Column(String(255), default=ThermostatGroup.Modes.HEATING, nullable=False)  # temporary placed here, will move to PID

    # valve = relationship('Valve', lazy='joined', backref='thermostat_associations')
    valve = relationship('Valve', lazy='joined', back_populates='thermostat_associations')
    thermostat = relationship('Thermostat', backref='valve_associations')


class Preset(Base):
    __tablename__ = 'preset'
    __table_args__ = {'sqlite_autoincrement': True}

    class Types(object):
        MANUAL = 'manual'
        AUTO = 'auto'
        AWAY = 'away'
        VACATION = 'vacation'
        PARTY = 'party'

    ALL_TYPES = [Types.MANUAL, Types.AUTO, Types.AWAY, Types.VACATION, Types.PARTY]
    DEFAULT_PRESET_TYPES = [Types.AWAY, Types.VACATION, Types.PARTY]
    DEFAULT_PRESETS = {ThermostatGroup.Modes.HEATING: dict(zip(DEFAULT_PRESET_TYPES, [16.0, 15.0, 22.0])),
                       ThermostatGroup.Modes.COOLING: dict(zip(DEFAULT_PRESET_TYPES, [25.0, 38.0, 25.0]))}
    TYPE_TO_SETPOINT = {Types.AWAY: 3,
                        Types.VACATION: 4,
                        Types.PARTY: 5}
    SETPOINT_TO_TYPE = {setpoint: preset_type
                        for preset_type, setpoint in TYPE_TO_SETPOINT.items()}

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String(255), nullable=False)  # Options: see Preset.Types
    heating_setpoint = Column(Float, default=14.0, nullable=False)
    cooling_setpoint = Column(Float, default=30.0, nullable=False)
    active = Column(Boolean, default=False, nullable=False)
    thermostat_id = Column(Integer, ForeignKey('thermostat.id', ondelete='CASCADE'), nullable=False)

    thermostat = relationship('Thermostat', back_populates='presets')


class DaySchedule(Base):
    __tablename__ = 'dayschedule'
    __table_args__ = {'sqlite_autoincrement': True}

    DEFAULT_SCHEDULE_TIMES = [0, 6 * 3600, 8 * 3600, 16 * 3600, 22 * 3600]
    DEFAULT_SCHEDULE = {ThermostatGroup.Modes.HEATING: dict(zip(DEFAULT_SCHEDULE_TIMES, [19.0, 21.0, 19.0, 21.0, 19.0])),
                        ThermostatGroup.Modes.COOLING: dict(zip(DEFAULT_SCHEDULE_TIMES, [26.0, 23.0, 26.0, 23.0, 26.0]))}

    id = Column(Integer, primary_key=True, autoincrement=True)
    index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    mode = Column(String(255), default=ThermostatGroup.Modes.HEATING, nullable=False)
    thermostat_id = Column(Integer, ForeignKey('thermostat.id', ondelete='CASCADE'), nullable=False)

    thermostat = relationship('Thermostat', back_populates='schedules')

    @property
    def schedule_data(self):  # type: () -> Dict[int, float]
        return {int(k): v for k, v in json.loads(self.content).items()}

    @schedule_data.setter
    def schedule_data(self, value):  # type: (Dict[int, float]) -> None
        self.content = json.dumps(value)

    def get_scheduled_temperature(self, seconds_in_day):  # type: (int) -> Optional[float]
        seconds_in_day = seconds_in_day % 86400
        data = self.schedule_data
        last_value = data.get(0)
        for key in sorted(data):
            if key > seconds_in_day:
                break
            last_value = data[key]
        return last_value

    def __str__(self):
        schedule = self.schedule_data
        schedules = []
        for offset in sorted(list(schedule.keys())):
            minutes = offset // 60
            schedules.append(('{0:02d}:{1:02d}'.format(minutes // 60, minutes % 60), schedule[offset]))
        return ', '.join('{0}: {1}'.format(s[0], s[1]) for s in schedules)


class Room(Base, MasterNumber):
    __tablename__ = 'room'
    __table_args__ = {'sqlite_autoincrement': True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=True)


class DataMigration(Base):
    __tablename__ = 'datamigration'
    __table_args__ = {'sqlite_autoincrement': True}

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    migrated = Column(Boolean, nullable=False)


class User(Base):
    __tablename__ = 'user'
    __table_args__ = {'sqlite_autoincrement': True}

    class UserRoles(object):
        SUPER = 'SUPER'
        USER = 'USER'
        ADMIN = 'ADMIN'
        TECHNICIAN = 'TECHNICIAN'
        COURIER = 'COURIER'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(255), nullable=False, unique=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    role = Column(String(255), default=UserRoles.USER, nullable=False)  # options USER, ADMIN, TECHNICIAN, COURIER, SUPER
    pin_code = Column(String(255), nullable=True, unique=True)
    language = Column(String(255), nullable=False)  # options: See languages
    password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    accepted_terms = Column(Integer, default=0, nullable=False)
    email = Column(String(255), nullable=True, unique=False)


class Screen(Base):
    __tablename__ = 'screen'
    __table_args__ = {'sqlite_autoincrement': True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(Integer, ForeignKey('room.id', ondelete='SET NULL'), nullable=True)
    name = Column(String(255), default='', nullable=False)
    in_use = Column(Boolean, nullable=False, default=True)
    type = Column(String(255), nullable=False)

    translational_steps = Column(Integer, nullable=True)
    rotational_steps = Column(Integer, nullable=True)

    source = Column(String(255), nullable=False)
    external_id = Column(String(255), nullable=False)
    plugin_id = Column(Integer, ForeignKey('plugin.id', ondelete='CASCADE'), nullable=True)

    room = relationship('Room', lazy='joined', innerjoin=False)  # type: RelationshipProperty[Optional[Room]]
    plugin = relationship('Plugin', lazy='joined', innerjoin=False)  # type: RelationshipProperty[Optional[Plugin]]

    def __str__(self):
        if self.name:
            return '{0} ({1})'.format(self.name, self.id)
        return str(self.id)