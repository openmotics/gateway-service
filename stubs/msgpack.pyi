from typing import IO, Any, Callable, Generic, Iterator, Optional, TypeVar

T = TypeVar('T')


class ExtType: ...


class Packer(Generic[T]):
    def __init__(self,
                 default: Optional[T] = None,
                 use_single_float=False,
                 autoreset=True,
                 use_bin_type=True,
                 strict_types=False,
                 datetime=False,
                 unicode_errors='strict') -> None:
        ...

    def pack(self, obj: T) -> bytes: ...


class Unpacker(Iterator[T]):
    def __init__(self,
                 file_like: IO[bytes],
                 read_size=0,
                 use_list=True,
                 raw=False,
                 timestamp=0,
                 strict_map_key=True,
                 object_hook=Callable[..., Any],
                 object_pairs_hook=Callable[..., Any],
                 list_hook=Callable[..., Any],
                 unicode_errors='strict',
                 max_buffer_size=104857600,
                 ext_hook=ExtType(),
                 max_str_len=-1,
                 max_bin_len=-1,
                 max_array_len=-1,
                 max_map_len=-1,
                 max_ext_len=-1) -> None:
        ...

    def __next__(self) -> T: ...

    def unpack(self) -> T: ...


def pack(obj: Any, stream: IO[bytes], **Any) -> None: ...
def packb(obj: Any, **Any) -> bytes: ...

def unpack(stream: IO[bytes], **Any) -> Any: ...
def unpackb(packed: bytes, **Any) -> Any: ...


# alias for compatibility to simplejson/marshal/pickle.
load = unpack
loads = unpackb

dump = pack
dumps = packb
