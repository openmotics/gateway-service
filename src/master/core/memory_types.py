# Copyright (C) 2019 OpenMotics BV
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
Contains memory (field) types
"""
from __future__ import absolute_import
import inspect
import logging
import ujson as json
import struct
from peewee import DoesNotExist
from threading import Lock
from ioc import INJECTED, Inject
from master.core.exceptions import InvalidMemoryChecksum

if False:  # MYPY
    from typing import Any, Dict, List, Optional, Union, Tuple, Callable, Set
    from master.core.basic_action import BasicAction
    from master.core.memory_file import MemoryFile

logger = logging.getLogger("openmotics")


class MemoryModelDefinition(object):
    """
    Represents a model definition
    """

    _cache_fields = {}  # type: Dict[str,Any]
    _cache_addresses = {}  # type: Dict[str,Any]
    _cache_lock = Lock()

    @Inject
    def __init__(self, id, memory_files=INJECTED, verbose=False):  # type: (Optional[int], Dict[str, MemoryFile], bool) -> None
        self._id = id
        self._id_field = self.__class__._get_id_field()  # TODO: Make sure that an id field is mandatory for id-lookups
        if self._id_field is not None:
            if id is None:
                raise RuntimeError('An id is mandatory')
            self._id_field.validate(self.__class__.__name__, id)
            setattr(self.__class__, 'id', property(lambda s: s._id))
        self._verbose = verbose
        self._memory_files = memory_files
        self._fields = []  # type: List[str]
        self._loaded_fields = set()  # type: Set[str]
        self._relations = []  # type: List[str]
        self._relations_cache = {}  # type: Dict[str, MemoryModelDefinition]
        self._compositions = []  # type: List[str]
        address_cache = self.__class__._get_address_cache(self._id)
        for field_name, field_type in self.__class__._get_field_dict().items():
            memory_field_container = MemoryFieldContainer(name=field_name,
                                                          memory_field=field_type,
                                                          memory_address=address_cache[field_name])
            if field_type._checksum is not None:
                memory_field_container.set_checksum_container(MemoryChecksumContainer(check=field_type._checksum._check,
                                                                                      field_container=MemoryFieldContainer(name=field_name,
                                                                                                                           memory_field=field_type._checksum._field,
                                                                                                                           memory_address=field_type._checksum._field.get_address(self._id)),
                                                                                      default=field_type._checksum._default))
            setattr(self, '_{0}'.format(field_name), memory_field_container)
            self._add_property(field_name)
            self._fields.append(field_name)
        for field_name, relation in self.__class__._get_relational_fields().items():
            relation_container = MemoryRelationContainer(instance_type=relation._instance_type,
                                                         id_spec=relation._id_spec)
            if relation._field is not None:
                relation_container.set_field_container(MemoryFieldContainer(name=field_name,
                                                                            memory_field=relation._field,
                                                                            memory_address=relation._field.get_address(self._id)))
            setattr(self, '_{0}'.format(field_name), relation_container)
            self._add_relation(field_name)
            self._relations.append(field_name)
        for field_name, composition in self.__class__._get_composite_fields().items():
            setattr(self, '_{0}'.format(field_name), CompositionContainer(composite_definition=composition,
                                                                          composition_width=composition._field.length * 8,
                                                                          field_container=MemoryFieldContainer(name=field_name,
                                                                                                               memory_field=composition._field,
                                                                                                               memory_address=composition._field.get_address(self._id))))
            self._add_composition(field_name)
            self._compositions.append(field_name)

    def __str__(self):
        return str(json.dumps(self.serialize(), indent=4))

    def serialize(self):  # type: () -> Dict[str, Any]
        data = {}
        if self._id is not None:
            data['id'] = self._id
        for field_name in self._fields:
            data[field_name] = getattr(self, field_name)
        for field_name in self._compositions:
            data[field_name] = getattr(self, field_name).serialize()
        return data

    def _add_property(self, field_name):  # type: (str) -> None
        setattr(self.__class__, '_{0}'.format(field_name), getattr(self, '_{0}'.format(field_name))._memory_field)
        setattr(self.__class__, field_name, property(lambda s: s._get_property(field_name),
                                                     lambda s, v: s._set_property(field_name, v)))

    def _get_property(self, field_name):  # type: (str) -> Any
        self._loaded_fields.add(field_name)
        field = getattr(self, '_{0}'.format(field_name))  # type: MemoryFieldContainer
        return field.decode()

    def _set_property(self, field_name, value):  # type: (str, Any) -> None
        self._loaded_fields.add(field_name)
        field = getattr(self, '_{0}'.format(field_name))  # type: MemoryFieldContainer
        field.encode(value)

    def _add_relation(self, field_name):  # type: (str) -> None
        setattr(self.__class__, field_name, property(lambda s: s._get_relation(field_name)))

    def _get_relation(self, field_name):  # type: (str) -> MemoryModelDefinition
        if field_name not in self._relations_cache:
            relation = getattr(self, '_{0}'.format(field_name))
            self._relations_cache[field_name] = relation.yield_instance(self._id)
        return self._relations_cache[field_name]

    def _add_composition(self, field_name):  # type: (str) -> None
        setattr(self.__class__, field_name, property(lambda s: s._get_composition(field_name)))

    def _get_composition(self, field_name):  # type: (str) -> CompositionContainer
        self._loaded_fields.add(field_name)
        return getattr(self, '_{0}'.format(field_name))

    def save(self, activate=True):  # type: (bool) -> None
        for field_name in self._loaded_fields:
            container = getattr(self, '_{0}'.format(field_name))  # type: Union[MemoryFieldContainer, CompositionContainer]
            if self._verbose:
                logger.info('Saving {0}({1}).{2}'.format(
                    self.__class__.__name__,
                    '' if self._id is None else self._id,
                    field_name
                ))
            container.save()
        if activate:
            for memory_file in self._memory_files.values():
                memory_file.activate()

    @classmethod
    def deserialize(cls, data):  # type: (Dict[str, Any]) -> MemoryModelDefinition
        instance_id = data['id']
        instance = cls(instance_id)
        for field_name, value in data.items():
            if field_name == 'id':
                pass
            elif field_name in instance._fields:
                setattr(instance, field_name, value)
            elif field_name in instance._relations:
                relation = getattr(instance, '_{0}'.format(field_name))
                instance._relations_cache[field_name] = relation.instance_type.deserialize(value)
            elif field_name in instance._compositions:
                composition = getattr(instance, field_name)
                composition._load(value)
            else:
                raise ValueError('Unknown field: {0}', field_name)
        return instance

    @classmethod
    def _get_fields(cls):  # type: () -> Dict[str, Any]
        """ Get the fields defined by an EepromModel child. """
        if cls.__name__ not in MemoryModelDefinition._cache_fields:
            MemoryModelDefinition._cache_fields[cls.__name__] = {'id': inspect.getmembers(cls, lambda f: isinstance(f, IdField)),
                                                                 'fields': inspect.getmembers(cls, lambda f: isinstance(f, MemoryField)),
                                                                 'enums': inspect.getmembers(cls, lambda f: isinstance(f, MemoryEnumDefinition)),
                                                                 'relations': inspect.getmembers(cls, lambda f: isinstance(f, MemoryRelation)),
                                                                 'compositions': inspect.getmembers(cls, lambda f: isinstance(f, CompositeMemoryModelDefinition))}
        return MemoryModelDefinition._cache_fields[cls.__name__]

    @classmethod
    def _get_id_field(cls):  # type: () -> Optional[IdField]
        """ Gets the classes ID field definition """
        fields = cls._get_fields()
        for _, field_type in fields['id']:
            return field_type
        return None

    @classmethod
    def _get_field_dict(cls):  # type: () -> Dict[str, Any]
        """
        Get a dict from the field name to the field type for each field defined by model
        """
        class_field_dict = {}
        fields = cls._get_fields()
        for name, field_type in fields['fields'] + fields['enums']:
            class_field_dict[name] = field_type
        return class_field_dict

    @classmethod
    def _get_relational_fields(cls):  # type: () -> Dict[str, Any]
        """
        Gets a dict of all relational fields
        """
        relation_field_dict = {}
        for name, field_type in cls._get_fields()['relations']:
            relation_field_dict[name] = field_type
        return relation_field_dict

    @classmethod
    def _get_composite_fields(cls):  # type: () -> Dict[str, Any]
        """
        Gets a dict of all composite fields
        """
        composite_field_dict = {}
        for name, field_type in cls._get_fields()['compositions']:
            composite_field_dict[name] = field_type
        return composite_field_dict

    @classmethod
    def _get_address_cache(cls, id):  # type: (Optional[int]) -> Any
        if cls.__name__ in MemoryModelDefinition._cache_addresses:
            class_cache = MemoryModelDefinition._cache_addresses[cls.__name__]
        else:
            with MemoryModelDefinition._cache_lock:
                class_cache = MemoryModelDefinition._cache_addresses.setdefault(cls.__name__, {})
        if id in class_cache:
            return class_cache[id]
        with MemoryModelDefinition._cache_lock:
            cache = {}
            for field_name, field_type in cls._get_fields()['fields'] + cls._get_fields()['enums']:
                cache[field_name] = field_type.get_address(id)
            class_cache[id] = cache
        return cache


class MemoryActivator(object):
    """ Holds a static method to activate memory """
    @staticmethod
    @Inject
    def activate(memory_files=INJECTED):  # type: (Dict[str, MemoryFile]) -> None
        for memory_file in memory_files.values():
            memory_file.activate()


class GlobalMemoryModelDefinition(MemoryModelDefinition):
    """
    Represents a model definition
    """

    def __init__(self):
        super(GlobalMemoryModelDefinition, self).__init__(None)


class MemoryFieldContainer(object):
    """
    This object holds the MemoryField and the data.
    """

    @Inject
    def __init__(self, name, memory_field, memory_address,  memory_files=INJECTED):
        # type: (str, MemoryField, MemoryAddress, Dict[str, MemoryFile]) -> None
        self._field_name = name
        self._memory_field = memory_field
        self._memory_address = memory_address
        self._memory_files = memory_files
        self._data = None  # type: Optional[bytearray]
        self._checksum_container = None  # type: Optional[MemoryChecksumContainer]

    def set_checksum_container(self, checksum_container):  # type: (MemoryChecksumContainer) -> None
        self._checksum_container = checksum_container

    def _read_data(self):  # type: () -> None
        self._data = self._memory_files[self._memory_address.memory_type].read([self._memory_address])[self._memory_address]

    def encode(self, value):  # type: (Any) -> None
        """ Encodes changes a high-level value such as a string or large integer into a memory byte array (array of 0 <= x <= 255) """
        if self._memory_field._read_only:
            raise AttributeError('The field `{0}` is read-only'.format(self._field_name))
        self._data = self._memory_field.encode(value)
        if self._checksum_container is not None:
            self._checksum_container.update(self._data)

    def decode(self):  # type: () -> Any
        """ Decodes a memory byte array (array of 0 <= x <= 255) into a high-level valuye shuch as a string or large integer """
        if self._data is None:
            self._read_data()
        if self._data is None:
            raise RuntimeError('No data was read from memory')
        if self._checksum_container is not None:
            if not self._checksum_container.is_valid(self._data):
                default = self._checksum_container._default
                if default is None:
                    raise InvalidMemoryChecksum('The field `{0}` fails its checksum'.format(self._field_name))
                return default
        return self._memory_field.decode(self._data)

    def save(self):  # type: () -> None
        if self._data is None:
            return
        self._memory_files[self._memory_address.memory_type].write({self._memory_address: self._data})
        if self._checksum_container is not None:
            self._checksum_container.save()


class MemoryField(object):
    """
    Defines a memory and provides encode/decode functions to convert this memory type from and to its memory representation.
    Besides these functions, the memory type also contains the address or address generator (in case the model has an id).
    """

    # TODO: See if this can inherit from Field or use Fields internally so the implementations are unified

    def __init__(self, memory_type, address_spec, length, limits=None, read_only=False, checksum=None):
        # type: (str, Union[Tuple[int, int], Callable[[int], Tuple[int, int]]], int, Optional[Tuple[int, int]], bool, Optional[MemoryChecksum]) -> None
        """
        Create an instance of an MemoryDataType with an address or an address generator.
        """
        self._address_tuple = None
        self._address_generator = None
        self._memory_type = memory_type
        self._read_only = read_only
        self._checksum = checksum
        self.length = length
        if limits is not None:
            self.limits = limits
        else:
            self.limits = (0, 2 ** (8 * length) - 1)

        if isinstance(address_spec, tuple):
            self._address_tuple = address_spec
        elif callable(address_spec):
            args = inspect.getargspec(address_spec).args
            if len(args) == 1:
                self._address_generator = address_spec
            else:
                raise TypeError('Parameter `address_spec` should be a function that takes an id and returns the same tuple.')
        else:
            raise TypeError('Parameter `address_spec` should be a tuple (page, offset) or a function that takes an id and returns the same tuple.')

    def get_address(self, id):  # type: (Optional[int]) -> MemoryAddress
        """
        Calculate the address for this field.
        """
        if id is None:
            if self._address_tuple is None:
                raise TypeError('MemoryField expects an id')
            page, offset = self._address_tuple
        else:
            if self._address_generator is None:
                raise TypeError('MemoryField did not expect an id')
            page, offset = self._address_generator(id)
        return MemoryAddress(self._memory_type, page, offset, self.length)

    def encode(self, data):  # type: (Any) -> bytearray
        """ Encodes changes a high-level value such as a string or large integer into a bytearray """
        raise NotImplementedError()

    def decode(self, value):  # type: (bytearray) -> Any
        """ Decodes a bytearray into a high-level valuye shuch as a string or large integer """
        raise NotImplementedError()

    def _check_limits(self, value):  # type: (Union[float, int]) -> None
        if value is None or not (self.limits[0] <= value <= self.limits[1]):
            raise ValueError('Value `{0}` out of limits: {1} <= value <= {2}'.format(value, self.limits[0], self.limits[1]))


class MemoryStringField(MemoryField):
    def __init__(self, memory_type, address_spec, length, read_only=False, checksum=None):
        super(MemoryStringField, self).__init__(memory_type=memory_type,
                                                address_spec=address_spec,
                                                length=length,
                                                read_only=read_only,
                                                checksum=checksum)

    def encode(self, value):  # type: (str) -> bytearray
        if len(value) > self.length:
            raise ValueError('Value {0} should be a string of {1} characters'.format(value, self.length))
        data = []
        for char in value:
            data.append(ord(char))
        data += [255] * (self.length - len(data))
        return bytearray(data)

    def decode(self, data):  # type: (bytearray) -> str
        while len(data) >= 1 and data[-1] in [0, 255]:
            data.pop()
        return ''.join([str(chr(item)) if 32 <= item <= 126 else ' ' for item in data])


class MemoryByteField(MemoryField):
    def __init__(self, memory_type, address_spec, read_only=False, checksum=None):
        super(MemoryByteField, self).__init__(memory_type=memory_type,
                                              address_spec=address_spec,
                                              read_only=read_only,
                                              checksum=checksum,
                                              length=1)

    def encode(self, value):  # type: (int) -> bytearray
        self._check_limits(value)
        return bytearray([value])

    def decode(self, data):  # type: (bytearray) -> int
        return data[0]


class MemoryWordField(MemoryField):
    def __init__(self, memory_type, address_spec, read_only=False, checksum=None):
        super(MemoryWordField, self).__init__(memory_type=memory_type,
                                              address_spec=address_spec,
                                              read_only=read_only,
                                              checksum=checksum,
                                              length=2)

    def encode(self, value):  # type: (int) -> bytearray
        self._check_limits(value)
        return bytearray(struct.pack('>H', value))

    def decode(self, data):  # type: (bytearray) -> int
        return struct.unpack('>H', data)[0]


class Memory3BytesField(MemoryField):
    def __init__(self, memory_type, address_spec, read_only=False, checksum=None):
        super(Memory3BytesField, self).__init__(memory_type=memory_type,
                                                address_spec=address_spec,
                                                read_only=read_only,
                                                checksum=checksum,
                                                length=3)

    def encode(self, value):  # type: (int) -> bytearray
        self._check_limits(value)
        return bytearray(struct.pack('>I', value))[-3:]

    def decode(self, data):  # type: (bytearray) -> int
        return struct.unpack('>I', bytearray([0]) + data)[0]


class _MemoryArrayField(MemoryField):
    def __init__(self, memory_type, address_spec, length, field, read_only, checksum):
        self._field = field(memory_type, address_spec)
        self._entry_length = length
        super(_MemoryArrayField, self).__init__(memory_type=memory_type,
                                                address_spec=address_spec,
                                                length=self._field.length * self._entry_length,
                                                read_only=read_only,
                                                checksum=checksum)

    def encode(self, value):  # type: (Any) -> bytearray
        if len(value) != self._entry_length:
            raise ValueError('Value `{0}` should be an array of {1} items with {2} <= item <= {3}'.format(value,
                                                                                                          self._entry_length,
                                                                                                          self._field.limits[0],
                                                                                                          self._field.limits[1]))
        data = bytearray()
        for item in value:
            data += self._field.encode(item)
        return data

    def decode(self, data):  # type: (bytearray) -> Any
        result = []
        for i in range(0, len(data), self._field.length):
            result.append(self._field.decode(data[i:i + self._field.length]))
        return result


class MemoryRawByteArrayField(_MemoryArrayField):
    def __init__(self, memory_type, address_spec, length, read_only=False, checksum=None):
        super(MemoryRawByteArrayField, self).__init__(memory_type=memory_type,
                                                      address_spec=address_spec,
                                                      length=length,
                                                      read_only=read_only,
                                                      checksum=checksum,
                                                      field=MemoryByteField)

    def encode(self, value):  # type: (bytearray) -> bytearray
        return super(MemoryRawByteArrayField, self).encode(list(value))

    def decode(self, data):  # type: (bytearray) -> bytearray
        return bytearray(super(MemoryRawByteArrayField, self).decode(data))


class MemoryByteArrayField(_MemoryArrayField):
    def __init__(self, memory_type, address_spec, length, field=None, read_only=False, checksum=None):
        if field is None:
            field = MemoryByteField
        super(MemoryByteArrayField, self).__init__(memory_type=memory_type,
                                                   address_spec=address_spec,
                                                   length=length,
                                                   field=field,
                                                   read_only=read_only,
                                                   checksum=checksum)

    def encode(self, value):  # type: (List[int]) -> bytearray
        return super(MemoryByteArrayField, self).encode(value)

    def decode(self, data):  # type: (bytearray) -> List[int]
        return super(MemoryByteArrayField, self).decode(data)


class MemoryWordArrayField(MemoryByteArrayField):
    def __init__(self, memory_type, address_spec, length, read_only=False, checksum=None):
        super(MemoryWordArrayField, self).__init__(memory_type=memory_type,
                                                   address_spec=address_spec,
                                                   length=length,
                                                   read_only=read_only,
                                                   checksum=checksum,
                                                   field=MemoryWordField)


class MemoryBasicActionField(MemoryField):
    def __init__(self, memory_type, address_spec, read_only=False, checksum=None):
        super(MemoryBasicActionField, self).__init__(memory_type=memory_type,
                                                     address_spec=address_spec,
                                                     read_only=read_only,
                                                     checksum=checksum,
                                                     length=6)

    def encode(self, value):  # type: (BasicAction) -> bytearray
        from master.core.basic_action import BasicAction  # Prevent circular import

        if not isinstance(value, BasicAction):
            raise ValueError('Value should be a BasicAction')
        return value.encode()

    def decode(self, data):  # type: (bytearray) -> BasicAction
        from master.core.basic_action import BasicAction  # Prevent circular import

        return BasicAction.decode(data)


class MemoryAddressField(MemoryField):
    def __init__(self, memory_type, address_spec, length=4, read_only=False, checksum=None):
        super(MemoryAddressField, self).__init__(memory_type=memory_type,
                                                 address_spec=address_spec,
                                                 length=length,
                                                 read_only=read_only,
                                                 checksum=checksum)

    def encode(self, value):  # type: (str) -> bytearray
        example = '.'.join(['ID{0}'.format(i) for i in range(self.length - 1, -1, -1)])
        error_message = 'Value `{0}` should be a string in the format of {1}, where 0 <= IDx <= 255'.format(value, example)
        parts = str(value).split('.')
        if len(parts) != self.length:
            raise ValueError(error_message)
        data = []
        for part in parts:
            try:
                int_part = int(part)
            except ValueError:
                raise ValueError(error_message)
            if not (0 <= int_part <= 255):
                raise ValueError(error_message)
            data.append(int_part)
        return bytearray(data)

    def decode(self, data):  # type: (bytearray) -> str
        return '.'.join('{0:03}'.format(item) for item in data)


class MemoryVersionField(MemoryAddressField):
    def __init__(self, memory_type, address_spec, read_only=False, checksum=None):
        super(MemoryVersionField, self).__init__(memory_type=memory_type,
                                                 address_spec=address_spec,
                                                 read_only=read_only,
                                                 checksum=checksum,
                                                 length=3)

    def decode(self, data):  # type: (bytearray) -> str
        return '.'.join(str(item) for item in data)


class IdField(object):
    def __init__(self, limits, field=None):
        # type: (Union[Tuple[int, int], Callable[[int], Tuple[int, int]]], Optional[MemoryField]) -> None
        self._limits = limits
        self._field = field
        if field is None:
            if not isinstance(limits, tuple):
                raise ValueError('When no fields are configured, a fixed limit should be given')
        elif not callable(limits):
            raise ValueError('Limits should be generated at runtime if a field is given')

    @Inject
    def validate(self, class_name, id):  # type: (str, Optional[int]) -> None
        if self._field is None:
            if not isinstance(self._limits, tuple):
                raise RuntimeError('Expected a fixed limit')
            limits = self._limits
        else:
            if not callable(self._limits):
                raise RuntimeError('Expected a limit generator')
            container = MemoryFieldContainer(name='id',
                                             memory_field=self._field,
                                             memory_address=self._field.get_address(None))
            limits = self._limits(container.decode())
        if id is None or not (limits[0] <= id <= limits[1]):
            if limits[0] > limits[1]:
                limit_info = 'No records available.'
            elif limits[0] == limits[1]:
                limit_info = 'Only one records available: {0}'.format(limits[0])
            else:
                limit_info = 'Available records: {0} <= id <= {1}'.format(limits[0], limits[1])
            raise DoesNotExist('Could not find {0}({1}). {2}'.format(class_name, '' if id is None else id, limit_info))


class MemoryRelation(object):
    def __init__(self, instance_type, id_spec, field=None):
        # type: (type, Callable[[int], int], Optional[MemoryField]) -> None
        self._instance_type = instance_type
        self._id_spec = id_spec
        self._field = field


class MemoryRelationContainer(object):
    def __init__(self, instance_type, id_spec):  # type: (type, Callable[[int], int]) -> None
        self.instance_type = instance_type
        self._id_spec = id_spec
        self._field_container = None  # type: Optional[MemoryFieldContainer]

    def set_field_container(self, field_container):  # type: (MemoryFieldContainer) -> None
        self._field_container = field_container

    def yield_instance(self, own_id):  # type: (int) -> Optional[MemoryModelDefinition]
        base_id = own_id
        if self._field_container is not None:
            base_id = self._field_container.decode()
        instance_id = self._id_spec(base_id)
        if instance_id is None:
            return None
        return self.instance_type(instance_id)

    def serialize(self):
        raise NotImplementedError()

    def save(self):  # type: () -> None
        raise NotImplementedError()


class MemoryAddress(object):
    """ Represents an address in the EEPROM/FRAM. Has a memory type, page, offset and length """

    def __init__(self, memory_type, page, offset, length):  # type: (str, int, int, int) -> None
        self.memory_type = memory_type
        self.page = page
        self.offset = offset
        self.length = length

    def __hash__(self):  # type: () -> int
        return ord(self.memory_type) + self.page * 256 + self.offset * 256 * 256 + self.length * 256 * 256 * 256

    def __str__(self):
        return 'Address({0}{1}, {2}, {3})'.format(self.memory_type, self.page, self.offset, self.length)

    def __eq__(self, other):
        if not isinstance(other, MemoryAddress):
            return False
        return hash(self) == hash(other)


class MemoryChecksum(object):
    class Types(object):
        INVERTED = 'inverted'

    def __init__(self, field, check, default=None):  # type: (MemoryField, str, Optional[Any]) -> None
        self._field = field
        self._check = check
        self._default = default


class MemoryChecksumContainer(object):
    def __init__(self, check, field_container, default):  # type: (str, MemoryFieldContainer, Optional[Any]) -> None
        self._check = check
        self._field_container = field_container
        self._default = default

    def is_valid(self, data):  # type: (bytearray) -> bool
        self._field_container._read_data()
        current_checksum = self._field_container._data
        if current_checksum is None:
            raise RuntimeError('No data was read from memory')
        if set(current_checksum) | set(data) in [{0}, {255}]:
            return True  # Ignore uninitialized data
        expected_checksum = self._calculate(data)
        if expected_checksum != current_checksum:
            logger.warning('Invalid memory checksum for `{0}`'.format(self._field_container._field_name))
            return False
        return True

    def update(self, data):  # type: (bytearray) -> None
        self._field_container._data = self._calculate(data)

    def save(self):
        if self._field_container is not None:
            self._field_container.save()

    def _calculate(self, data):  # type: (bytearray) -> bytearray
        if self._check == MemoryChecksum.Types.INVERTED:
            return bytearray([value ^ 255 for value in data])
        raise RuntimeError('Unknown checksum type')


class CompositeField(object):
    def decompose(self, value):  # type: (int) -> Any
        """ Decomposes a value out of the given composite value """
        raise NotImplementedError()

    def compose(self, base_value, value, composition_width):  # type: (int, Any, int) -> Any
        """ Composes a value onto a base (current) value """
        raise NotImplementedError()


class CompositeNumberField(CompositeField):
    def __init__(self, start_bit, width, value_offset=0, value_factor=1, max_value=None):
        # type: (int, int, int, int, Optional[int]) -> None
        super(CompositeNumberField, self).__init__()
        self._mask = 2 ** width - 1 << start_bit
        self._start_bit = start_bit
        if max_value is None:
            self._max_value = 2 ** width - 1
        else:
            self._max_value = max_value
        self._value_offset = value_offset
        self._value_factor = value_factor

    def decompose(self, value):  # type: (int) -> Optional[Any]
        return self._decompose(value)

    def _decompose(self, value):  # type: (int) -> Optional[Any]
        value = (value & self._mask) >> self._start_bit
        if self._max_value is None or 0 <= value <= self._max_value:
            return (value * self._value_factor) - self._value_offset
        return None

    def compose(self, current_composition, value, composition_width):  # type: (int, Any, int) -> int
        return self._compose(current_composition, value, composition_width)

    def _compose(self, current_composition, value, composition_width):  # type: (int, Any, int) -> int
        current_value = self._decompose(current_composition)
        if value == current_value:
            return current_composition
        processed_value = (value + self._value_offset) // self._value_factor
        if self._max_value is not None and not (0 <= processed_value <= self._max_value):
            raise ValueError('Value `{0}` (original `{1}`) out of limits: 0 <= value <= {2}'.format(processed_value, value, self._max_value))
        composing_value = (processed_value << self._start_bit) & self._mask
        current_composition = current_composition & ~self._mask & (2 ** composition_width - 1)
        return current_composition | composing_value


class CompositeBitField(CompositeNumberField):
    def __init__(self, bit):
        super(CompositeBitField, self).__init__(bit, 1)

    def decompose(self, value):  # type: (int) -> bool
        decomposed_value = super(CompositeBitField, self)._decompose(value)
        return decomposed_value == 1

    def compose(self, current_composition, value, composition_width):  # type: (int, bool, int) -> int
        value_to_compose = 1 if value else 0
        return super(CompositeBitField, self)._compose(current_composition, value_to_compose, composition_width)


class CompositeMemoryModelDefinition(object):
    """
    Represents a composite model definition. This class (only) holds composite fields
    """

    _cache_fields = {}  # type: Dict[str,Any]

    def __init__(self, field):
        self._field = field

    @classmethod
    def _get_field_names(cls):
        """ Get the field names defined by an MemoryModel child. """
        if cls.__name__ not in CompositeMemoryModelDefinition._cache_fields:
            CompositeMemoryModelDefinition._cache_fields[cls.__name__] = [entry[0] for entry in inspect.getmembers(cls, lambda f: isinstance(f, CompositeField))]
        return CompositeMemoryModelDefinition._cache_fields[cls.__name__]


class CompositionContainer(object):
    """
    This object holds the MemoryField and the data.
    """

    def __init__(self, composite_definition, composition_width, field_container):
        # type: (CompositeMemoryModelDefinition, int, MemoryFieldContainer) -> None
        self._composite_definition = composite_definition
        self._composition_width = composition_width
        self._field_container = field_container
        self._fields = []
        for field_name in self._composite_definition.__class__._get_field_names():
            self._add_property(field_name)
            self._fields.append(field_name)

    def _add_property(self, field_name):  # type: (str) -> None
        setattr(self.__class__, field_name, property(lambda s: s._get_property(field_name),
                                                     lambda s, v: s._set_property(field_name, v)))

    def _get_property(self, field_name):  # type: (str) -> Any
        field = getattr(self._composite_definition, field_name)
        return field.decompose(self._field_container.decode())

    def _set_property(self, field_name, value):  # type: (str, Any) -> None
        field = getattr(self._composite_definition, field_name)
        current_composition = self._field_container.decode()
        self._field_container.encode(field.compose(current_composition, value, self._composition_width))

    def _load(self, data):  # type: (Dict[str, Any]) -> None
        for field_name, value in data.items():
            if field_name == 'id':
                pass
            elif field_name in self._fields:
                self._set_property(field_name, value)
            else:
                raise ValueError('Unknown field: {0}', field_name)

    def serialize(self):  # type: () -> Dict[str, Any]
        data = {}
        for field_name in self._fields:
            data[field_name] = self._get_property(field_name)
        return data

    def save(self):
        self._field_container.save()


class MemoryEnumDefinition(object):
    """
    This object represents an enum
    """
    def __init__(self, field, read_only=False, checksum=None):  # type: (MemoryField, bool, Optional[MemoryChecksum]) -> None
        self._read_only = read_only
        self._field = field
        self._checksum = checksum
        self._entries = [entry for _, entry in inspect.getmembers(self, lambda f: isinstance(f, EnumEntry))]  # type: List[EnumEntry]

    def get_address(self, id):  # type: (int) -> MemoryAddress
        return self._field.get_address(id)

    def encode(self, value):  # type: (Union[str, EnumEntry]) -> bytearray
        found_entry = None  # type: Optional[EnumEntry]
        for entry in self._entries:
            if value == entry:
                found_entry = entry
                break
        if found_entry is None:
            raise ValueError('Value {0} is invalid'.format(value))
        # Use original entry to make sure only the prefedined values are used
        return self._field.encode(found_entry.values[0])

    def decode(self, data):  # type: (bytearray) -> EnumEntry
        decoded_field_value = self._field.decode(data)
        found_entry = None  # type: Optional[EnumEntry]
        for entry in self._entries:
            if decoded_field_value in entry.values:
                found_entry = entry
                break
            if found_entry is None and entry.default:
                found_entry = entry
        if found_entry is None:
            raise ValueError('Could not decode {0} to the correct enum entry'.format(decoded_field_value))
        return found_entry


class EnumEntry(object):
    def __init__(self, name, values, default=False):  # type: (str, List[int], bool) -> None
        self._name = name
        self.values = values
        self.default = default

    def __eq__(self, other):
        if isinstance(other, str):
            return self._name == other
        if not isinstance(other, EnumEntry):
            return False
        return self._name == other._name

    def __str__(self):
        return self._name

    def __repr__(self):
        return self._name
