import sys
import pdb
from math import ceil
from io import BytesIO
from binascii import hexlify
from struct import pack, unpack
from collections import ChainMap, OrderedDict, Sequence

__version__ = '0.9.5'

__all__ = ['Construct', 'Subconstruct', 'Context', 'Error',
           'BuildingError', 'ParsingError', 'SizeofError', 'ContextualError',
           'Pass', 'Flag', 'Bytes', 'Integer', 'Float', 'Padding',
           'Repeat', 'RepeatExactly', 'Adapted', 'Prefixed', 'Padded',
           'Aligned', 'StringEncoded', 'String', 'PascalString', 'CString',
           'Line', 'Struct', 'Contextual', 'Computed', 'BitFields', 'Const',
           'Raise', 'If', 'Switch', 'Enum', 'Offset', 'Tell', 'Checksum',
           'Debug']

CLASS_NAMESPACE_ORDERED = sys.version_info >= (3, 6)


# Base classes.
class Construct:
    """
    Base class for all kinds of constructs.

    Subclasses must implement the following methods:

        * _build_stream(self, obj, stream, context)
        * _parse_stream(self, stream, context)
        * _sizeof(self, context)
        * _repr(self)

    """
    __slots__ = ('_embedded',)

    def __init__(self):
        self._embedded = False

    def build(self, obj, context=None) -> bytes:
        """
        Build bytes from the python object.

        :param obj: Python object to build bytes from.
        :param context: Optional context dictionary.
        """
        stream = BytesIO()
        self.build_stream(obj, stream, context)
        return stream.getvalue()

    def parse(self, data: bytes, context=None):
        """
        Parse some python object from the data.

        :param data: Data to be parsed.
        :param context: Optional context dictionary.
        """
        stream = BytesIO(data)
        return self.parse_stream(stream, context)

    def build_stream(self, obj, stream: BytesIO, context=None) -> None:
        """
        Build bytes from the python object into the stream.

        :param obj: Python object to build bytes from.
        :param stream: A ``io.BytesIO`` instance to write bytes into.
        :param context: Optional context dictionary.
        """
        if context is None:
            context = Context()
        if not isinstance(context, Context):
            context = Context(context)
        try:
            self._build_stream(obj, stream, context)
        except Error:
            raise
        except Exception as exc:
            raise BuildingError(str(exc))

    def parse_stream(self, stream: BytesIO, context=None):
        """
        Parse some python object from the stream.

        :param stream: Stream from which the data is read and parsed.
        :param context: Optional context dictionary.
        """
        if context is None:
            context = Context()
        if not isinstance(context, Context):
            context = Context(context)
        try:
            return self._parse_stream(stream, context)
        except Error:
            raise
        except Exception as exc:
            raise ParsingError(str(exc))

    def sizeof(self, context=None) -> int:
        """
        Return the size of the construct in bytes.

        :param context: Optional context dictionary.
        """
        if context is None:
            context = Context()
        if not isinstance(context, Context):
            context = Context(context)
        try:
            return self._sizeof(context)
        except Error:
            raise
        except Exception as exc:
            raise SizeofError(str(exc))

    def __repr__(self):
        return self._repr()

    def __getitem__(self, item):
        """
        Used to make repeaters of constructs:

            SomeConstruct()[2:5] == Repeat(SomeConstruct(), 2, 5)

        """
        if isinstance(item, slice):
            if item.step is not None:
                raise ValueError('cannot make a Repeat with a step')
            return Repeat(self, item.start, item.stop)
        if isinstance(item, int):
            return RepeatExactly(self, item)
        raise ValueError(
            'can make a Repeat only from an int or a slice, got {!r}'.format(
                type(item)
            )
        )

    def _build_stream(self, obj, stream, context):  # pragma: nocover
        raise NotImplementedError

    def _parse_stream(self, stream, context):  # pragma: nocover
        raise NotImplementedError

    def _sizeof(self, context):  # pragma: nocover
        raise NotImplementedError

    def _repr(self):  # pragma: nocover
        raise NotImplementedError


class Subconstruct(Construct):
    """
    Non-trivial constructs often wrap other constructs and add
    transformations on top of them. This class helps to reduce boilerplate
    by providing default implementations for build, parse and sizeof:
    it proxies calls to the provided construct.

    Note that _repr still has to be implemented.

    :param construct: Wrapped construct.

    """
    __slots__ = Construct.__slots__ + ('construct',)

    def __init__(self, construct: Construct):
        super().__init__()
        self.construct = construct
        if construct._embedded:
            self._embedded = True

    def _build_stream(self, obj, stream, context):
        return self.construct._build_stream(obj, stream, context)

    def _parse_stream(self, stream, context):
        return self.construct._parse_stream(stream, context)

    def _sizeof(self, context):
        return self.construct._sizeof(context)

    def _repr(self):  # pragma: nocover
        raise NotImplementedError


class Context(ChainMap):
    """
    Special object that tracks building/parsing process, contains relevant
    values to build and already parsed values: fields parameters can depend
    of them via a contextual function instead of being statically defined.
    """


class Error(Exception):
    """
    Generic error, base class for all library errors.
    """


class BuildingError(Error):
    """
    Raises when building fails.
    """


class ParsingError(Error):
    """
    Raises when parsing fails.
    """


class SizeofError(Error):
    """
    Raises when sizeof fails.
    """


class ContextualError(Error):
    """
    Raises when a contextual function fails.
    """


# Primitive constructs
class Pass(Construct):
    r"""
    The most simplest construct ever: it does nothing when building
    or parsing, its size is 0.
    Useful as default cases for conditional constructs (Enum, Switch, If, etc).

        >>> p = Pass()
        >>> p
        Pass()
        >>> p.build('foo')
        b''
        >>> p.parse(b'bar')
        >>> p.sizeof()
        0

    """
    __slots__ = Construct.__slots__

    def _build_stream(self, obj, stream, context):
        return obj

    def _parse_stream(self, stream, context):
        pass

    def _sizeof(self, context):
        return 0

    def _repr(self):
        return 'Pass()'


class Flag(Construct):
    r"""
    Build and parse a single byte, interpreting 0 as ``False``
    and everything else as ``True``.

        >>> f = Flag()
        >>> f
        Flag()
        >>> f.build(True)
        b'\x01'
        >>> f.parse(b'\x00')
        False
        >>> f.parse(b'\x10')
        True
        >>> f.sizeof()
        1

    """
    __slots__ = Construct.__slots__

    def _build_stream(self, obj, stream, context):
        stream.write(b'\x01' if obj else b'\x00')

    def _parse_stream(self, stream, context):
        data = stream.read(1)
        if data == b'':
            raise ParsingError(
                'could not read enough bytes, expected 1, found 0'
            )
        return data != b'\x00'

    def _sizeof(self, context):
        return 1

    def _repr(self):
        return 'Flag()'


class Bytes(Construct):
    """
    Build and parse raw bytes with the specified length.

        >>> b = Bytes(3)
        >>> b
        Bytes(3)
        >>> b.build(b'foo')
        b'foo'
        >>> b.parse(b'bar')
        b'bar'
        >>> b.build(b'foobar')
        Traceback (most recent call last):
        ...
        structures.BuildingError: must build 3 bytes, got 6
        >>> b.sizeof()
        3

    ``ValueError`` is raised when length is less that -1:

        >>> Bytes(-10)
        Traceback (most recent call last):
        ...
        ValueError: length must be >= -1, got -10

    If length is omitted (or is -1), parsing consumes the stream to its end:

        >>> stream = BytesIO(b'foobar')
        >>> b = Bytes()
        >>> b.parse_stream(stream)
        b'foobar'
        >>> stream.read(1)
        b''
        >>> b.sizeof()
        Traceback (most recent call last):
        ...
        structures.SizeofError: Bytes() has no fixed size

    :param length: a number of bytes to build and to parse, if -1 then parsing
    consumes the stream to its end (see examples).

    """
    __slots__ = Construct.__slots__ + ('length',)

    def __init__(self, length: int = -1):
        super().__init__()
        if length < -1:
            raise ValueError('length must be >= -1, got {}'.format(length))
        self.length = length

    def _build_stream(self, obj: bytes, stream, context):
        if self.length == 1 and isinstance(obj, int):
            # Iterating over bytes gives ints, not bytes. Let's fix it.
            obj = bytes([obj])
        if self.length != -1 and len(obj) != self.length:
            raise BuildingError('must build {!r} bytes, got {!r}'.format(
                self.length, len(obj)
            ))
        stream.write(obj)

    def _parse_stream(self, stream, context) -> bytes:
        obj = stream.read(self.length)
        if self.length != -1 and len(obj) != self.length:
            raise ParsingError(
                'could not read enough bytes, expected {}, found {}'.format(
                    self.length, len(obj)
                )
            )
        return obj

    def _sizeof(self, context):
        if self.length == -1:
            raise SizeofError('Bytes() has no fixed size')
        return self.length

    def _repr(self):
        return 'Bytes({})'.format('' if self.length == -1 else self.length)


class Integer(Construct):
    r"""
    Build bytes from integers, parse integers from bytes.

        >>> i = Integer(1, byteorder='big', signed=False)
        >>> i
        Integer(1, byteorder='big', signed=False)
        >>> i.build(0xff)
        b'\xff'
        >>> i.parse(b'\x10')
        16
        >>> i.sizeof()
        1

        >>> Integer(1, 'little').build(0xff)
        b'\xff'

        >>> Integer(2, 'little').build(0xff)
        b'\xff\x00'
        >>> Integer(2, 'big').build(0xff)
        b'\x00\xff'

        >>> Integer(2, 'little', signed=True).build(-0x10ff)
        b'\x01\xef'

        >>> # pypy3 gives a different error message
        >>> # argument out of range for 1-byte integer format
        >>> # python3 gives
        >>> # ubyte format requires 0 <= number <= 255
        >>> Integer(1).build(-1)
        Traceback (most recent call last):
        ...
        structures.BuildingError: ...

        >>> Integer(3)
        Traceback (most recent call last):
        ...
        ValueError: length must be 1, 2, 4, or 8, got 3

        >>> Integer(1, 'custom')
        Traceback (most recent call last):
        ...
        ValueError: byteorder must be 'big' or 'little', got 'custom'

    :param length: the integer is represented using so many number of bytes.
    Currently only 1, 2, 4, and 8 bytes are supported.

    :param byteorder: the byteorder argument determines the byte order used
    to represent the integer. If byteorder is 'big', the most significant
    byte is at the beginning of the byte array. If byteorder is 'little',
    the most significant byte is at the end of the byte array. To request
    the native byte order of the host system, use `sys.byteorder`
    as the byte order value.

    :param signed: The signed keyword-only argument determines whether
    two's complement is used to represent the integer. If signed is False
    and a negative integer is given, a struct.error is raised, wrapped
    in a BuildingError/ParsingError.

    """
    __slots__ = Construct.__slots__ + ('length', 'byteorder', 'signed', '_fmt')

    def __init__(self, length: int, byteorder: str = 'big',
                 signed: bool = False):
        super().__init__()
        if length not in (1, 2, 4, 8):
            raise ValueError(
                'length must be 1, 2, 4, or 8, got {}'.format(length)
            )
        self.length = length
        if byteorder not in ('big', 'little'):
            raise ValueError("byteorder must be 'big' or 'little'"
                             ', got {!r}'.format(byteorder))
        self.byteorder = byteorder
        self.signed = signed
        self._fmt = ('>' if byteorder == 'big' else '<') + {
            (1, True): 'b',
            (1, False): 'B',
            (2, True): 'h',
            (2, False): 'H',
            (4, True): 'l',
            (4, False): 'L',
            (8, True): 'q',
            (8, False): 'Q',
        }[(length, signed)]

    def _build_stream(self, obj: int, stream, context):
        stream.write(pack(self._fmt, obj))

    def _parse_stream(self, stream, context):
        data = stream.read(self.length)
        return unpack(self._fmt, data)[0]

    def _sizeof(self, context):
        return self.length

    def _repr(self):
        return 'Integer({}, byteorder={!r}, signed={})'.format(
            self.length, self.byteorder, self.signed,
        )


class Float(Construct):
    r"""
    Build bytes from floats, parse floats from bytes.

        >>> i = Float(4, byteorder='big')
        >>> i
        Float(4, byteorder='big')
        >>> i.build(2.2)
        b'@\x0c\xcc\xcd'
        >>> i.parse(b'\x01\x02\x03\x04')
        2.387939260590663e-38
        >>> i.sizeof()
        4

        >>> Float(8, 'little').build(-1970.31415)
        b"'\xa0\x89\xb0A\xc9\x9e\xc0"

    Providing invalid parameters results in a ValueError:

        >>> Float(5)
        Traceback (most recent call last):
        ...
        ValueError: length must be 4 or 8, got 5
        >>> Float(4, byteorder='native')
        Traceback (most recent call last):
        ...
        ValueError: byteorder must be 'big' or 'little', got 'native'

    :param length: the float is represented using so many number of bytes.
        Currently only 4 and 8 bytes are supported.

    :param byteorder: the byteorder argument determines the byte order used
        to represent the float. If byteorder is 'big', the most significant
        byte is at the beginning of the byte array. If byteorder is 'little',
        the most significant byte is at the end of the byte array. To request
        the native byte order of the host system, use `sys.byteorder`
        as the byte order value.

    """
    __slots__ = Construct.__slots__ + ('length', 'byteorder', '_fmt')

    def __init__(self, length: int, byteorder: str = 'big'):
        super().__init__()
        if length not in (4, 8):
            raise ValueError('length must be 4 or 8, got {}'.format(length))
        self.length = length
        if byteorder not in ('big', 'little'):
            raise ValueError("byteorder must be 'big' or 'little'"
                             ', got {!r}'.format(byteorder))
        self.byteorder = byteorder
        _format_map = {
            (4, 'big'): '>f',
            (4, 'little'): '<f',
            (8, 'big'): '>d',
            (8, 'little'): '<d',
        }
        self._fmt = _format_map[(length, byteorder)]

    def _build_stream(self, obj: float, stream, context):
        stream.write(pack(self._fmt, obj))

    def _parse_stream(self, stream, context) -> float:
        data = stream.read(self.length)
        return unpack(self._fmt, data)[0]

    def _sizeof(self, context):
        return self.length

    def _repr(self):
        return 'Float({}, byteorder={!r})'.format(self.length, self.byteorder)


class Padding(Subconstruct):
    r"""
    Null bytes that are being ignored during building/parsing.

        >>> import os
        >>> p = Padding(4)
        >>> p
        Padding(4, padchar=b'\x00', direction='right')
        >>> p.build(os.urandom(16))
        b'\x00\x00\x00\x00'
        >>> p.parse(b'\x00\x00\x00\x00')
        >>> p.sizeof()
        4

    :param padchar: Pad using this char. Default is b'\x00' (zero byte).

    :param direction: Pad in this direction. Must be 'right', 'left',
    or 'center'. Default is 'right'.

    """
    __slots__ = Subconstruct.__slots__

    def __init__(self, length: int, padchar=b'\x00', direction='right'):
        super().__init__(Padded(Pass(), length, padchar, direction))

    def _repr(self):
        padded = self.construct  # type: Padded
        return 'Padding({}, padchar={!r}, direction={!r})'.format(
            padded.length, padded.padchar, padded.direction,
        )


# Adapters.
class Repeat(Subconstruct):
    r"""
    Repeat a construct for the specified range of times (semantics follows
    built-in ``range`` function except the step is always 1
    and negative values can't be specified).

        >>> r = Repeat(Flag(), 1, 4)
        >>> r
        Repeat(Flag(), start=1, stop=4)
        >>> r.build([True, True])
        b'\x01\x01'
        >>> r.parse(b'\x00\x01\x00')
        [False, True, False]
        >>> r.sizeof()
        Traceback (most recent call last):
        ...
        structures.SizeofError: cannot determine size of variable sized Repeat

    A predicate function can be specified to conditionally stop repeating.
    This function should accept a single argument of all accumulated
    items.

        >>> r = Repeat(Flag(), 1, 5, until=lambda obj: not obj[-1])
        >>> r
        Repeat(Flag(), start=1, stop=5, until=<function <lambda> at ...>)
        >>> r.build([True, True, False, True])
        b'\x01\x01\x00'
        >>> r.parse(b'\x01\x00\x00')
        [True, False]

    Note that the last element (which caused the repeat to stop) is included
    in the return list.

    The specified boundaries are mandatory:

        >>> r = Repeat(Flag(), 3, 5, until=lambda items: not items[-1])
        >>> r.build([True])
        Traceback (most recent call last):
        ...
        structures.BuildingError: length of the object to build must be in range [3, 5), got 1
        >>> r.parse(b'\x01\x01')
        Traceback (most recent call last):
        ...
        structures.ParsingError: required to parse at least 3 of Flag(), parsed 2 instead; error was: could not read enough bytes, expected 1, found 0
        >>> r.parse(b'\x00')
        Traceback (most recent call last):
        ...
        structures.ParsingError: required to parse at least 3 of Flag(), parsed 1 instead; exited due to 'until' predicate

    An alternative slice-based syntax can be used:

        >>> Flag()[2:5]
        Repeat(Flag(), start=2, stop=5)

    Providing invalid repeat parameters will throw a ValueError:

        >>> Repeat(Flag(), -1, 0)
        Traceback (most recent call last):
        ...
        ValueError: start must be >= 0, got -1
        >>> Repeat(Flag(), 0, -1)
        Traceback (most recent call last):
        ...
        ValueError: stop must be >= 0, got -1
        >>> Repeat(Flag(), 6, 2)
        Traceback (most recent call last):
        ...
        ValueError: stop must be >= start
        >>> Flag()[2:5:2]
        Traceback (most recent call last):
        ...
        ValueError: cannot make a Repeat with a step
        >>> Flag()['foo']
        Traceback (most recent call last):
        ...
        ValueError: can make a Repeat only from an int or a slice, got <class 'str'>

    :param construct: Construct to repeat.

    :param start: Must repeat build/parse at least this number of times.
    Must not be negative.

    :param stop: Must repeat build/parse at most this number of times.
    Must not be negative and must be greater than `start`.

    :param until: A predicate function of a single argument (list of items
    built/parsed so far), called during building/parsing and if the returned
    value is True, stops building/parsing. Default is None, meaning no
    predicate function is called during building/parsing.

    """
    __slots__ = Subconstruct.__slots__ + ('start', 'stop', 'until')

    def __init__(self, construct: Construct, start: int, stop: int,
                 until: callable = None):
        super().__init__(construct)
        if start < 0:
            raise ValueError('start must be >= 0, got {}'.format(start))
        self.start = start
        if stop < 0:
            raise ValueError('stop must be >= 0, got {}'.format(stop))
        self.stop = stop
        if stop < start:
            raise ValueError('stop must be >= start')
        self.until = until

    def _build_stream(self, obj: Sequence, stream, context):
        if not self.start <= len(obj) < self.stop:
            raise BuildingError(
                'length of the object to build must be in range '
                '[{}, {}), got {}'.format(self.start, self.stop, len(obj))
            )
        predicate = self.until
        items = []
        build_stream = self.construct._build_stream
        for item in obj:
            build_stream(item, stream, context)
            items.append(item)
            if predicate is not None and predicate(items):
                break

    def _parse_stream(self, stream, context) -> list:
        predicate = self.until
        obj = []
        parse_stream = self.construct._parse_stream
        stop = self.stop - 1
        try:
            while len(obj) < stop:
                item = parse_stream(stream, context)
                obj.append(item)
                if predicate is not None and predicate(obj):
                    break
        except ParsingError as exc:
            if len(obj) < self.start:
                raise ParsingError(
                    'required to parse at least {} of {}, '
                    'parsed {} instead; error was: {}'.format(
                        self.start, self.construct, len(obj), exc
                    )
                )
            return obj
        if len(obj) < self.start:
            raise ParsingError(
                'required to parse at least {} of {}, parsed '
                "{} instead; exited due to 'until' predicate".format(
                    self.start, self.construct, len(obj)
                )
            )
        return obj

    def _sizeof(self, context):
        if self.start != self.stop - 1 or self.until is not None:
            raise SizeofError(
                'cannot determine size of variable sized Repeat'
            )
        return self.start * self.construct._sizeof(context)

    def _repr(self):
        if self.until is None:
            return 'Repeat({}, start={}, stop={})'.format(
                self.construct, self.start, self.stop
            )
        return 'Repeat({}, start={}, stop={}, until={})'.format(
            self.construct, self.start, self.stop, self.until
        )


class RepeatExactly(Repeat):
    r"""
    Repeat the specified construct exactly n times.

        >>> r = RepeatExactly(Flag(), 3)
        >>> r
        RepeatExactly(Flag(), 3)
        >>> r.build([True, False, True])
        b'\x01\x00\x01'
        >>> r.parse(b'\x00\x01\x00')
        [False, True, False]
        >>> r.sizeof()
        3

    An alternative slice-based syntax can be used:

        >>> Flag()[3]
        RepeatExactly(Flag(), 3)

    :param construct: Construct to repeat.

    :param n: Repeat building/parsing exactly this number of times.

    :param until: A predicate function of a single argument (list of items
    built/parsed so far), called during building/parsing and if the returned
    value is True, stops building/parsing. Default is None, meaning no
    predicate function is called during building/parsing.

    """
    __slots__ = Repeat.__slots__

    def __init__(self, construct: Construct, n: int, until: callable = None):
        super().__init__(construct, n, n + 1, until)

    def _repr(self):
        return 'RepeatExactly({}, {})'.format(self.construct, self.start)


class Adapted(Subconstruct):
    r"""
    Adapter helps to transform objects before building and/or after parsing
    of the provided construct.

        >>> a = Adapted(Flag(),
        ...     before_build=lambda obj: obj != 'no',
        ...     after_parse=lambda obj: 'yes' if obj else 'no',
        ... )
        >>> a
        Adapted(Flag(), before_build=<function <lambda> at ...>, after_parse=<function <lambda> at ...>)
        >>> a.build('yes')
        b'\x01'
        >>> a.parse(b'\x00')
        'no'
        >>> a.sizeof()
        1

    :param construct: Construct to adapt.

    :param before_build: A function of a single argument, called before
    building bytes from an object.
    Default is None, meaning no building adaption is performed.

    :param after_parse: A function of a single argument, called after parsing
    an object from bytes.
    Default is None, meaning no parsing adaption is performed.

    """
    __slots__ = Subconstruct.__slots__ + ('before_build', 'after_parse')

    def __init__(self, construct: Construct,
                 before_build: callable = None, after_parse: callable = None):
        super().__init__(construct)
        self.before_build = before_build
        self.after_parse = after_parse

    def _build_stream(self, obj, stream, context):
        if self.before_build is not None:
            obj = self.before_build(obj)
        return self.construct._build_stream(obj, stream, context)

    def _parse_stream(self, stream, context):
        obj = self.construct._parse_stream(stream, context)
        if self.after_parse is not None:
            obj = self.after_parse(obj)
        return obj

    def _repr(self):
        return 'Adapted({}, before_build={!r}, after_parse={!r})'.format(
            self.construct, self.before_build, self.after_parse,
        )


class Prefixed(Subconstruct):
    r"""
    Length-prefixed construct.
    Parses the length field first, then reads that amount of bytes
    and parses the provided construct using only those bytes.
    Constructs that consume entire remaining stream (like Bytes()) are
    constrained to consuming only the specified amount of bytes.
    When building, data is prefixed by its length.

        >>> p = Prefixed(Bytes(), Integer(1))
        >>> p
        Prefixed(Bytes(), length_field=Integer(1, byteorder='big', signed=False))
        >>> p.build(b'foo')
        b'\x03foo'
        >>> p.parse(b'\x06foobar')
        b'foobar'
        >>> p.sizeof()
        Traceback (most recent call last):
        ...
        structures.SizeofError: Bytes() has no fixed size
        >>> p.parse(b'\x06baz')
        Traceback (most recent call last):
        ...
        structures.ParsingError: could not read enough bytes, expected 6, found 3

    :param construct: Construct to be prefixed with its length.

    :param length_field: Construct used to build/parse the length.

    """
    __slots__ = Subconstruct.__slots__ + ('length_field',)

    def __init__(self, construct: Construct, length_field: Construct):
        super().__init__(construct)
        self.length_field = length_field

    def _build_stream(self, obj, stream, context):
        self.length_field._build_stream(len(obj), stream, context)
        return self.construct._build_stream(obj, stream, context)

    def _parse_stream(self, stream, context):
        length = self.length_field._parse_stream(stream, context)
        data = stream.read(length)
        if len(data) != length:
            raise ParsingError(
                'could not read enough bytes, expected {}, found {}'.format(
                    length, len(data)
                )
            )
        stream2 = BytesIO(data)
        return self.construct._parse_stream(stream2, context)

    def _sizeof(self, context):
        length_size = self.length_field._sizeof(context)
        return length_size + self.construct._sizeof(context)

    def _repr(self):
        return 'Prefixed({}, length_field={})'.format(
            self.construct, self.length_field,
        )


class Padded(Subconstruct):
    r"""
    Appends additional null bytes to achieve a fixed length.

        >>> p = Padded(Bytes(3), 6)
        >>> p
        Padded(Bytes(3), length=6, padchar=b'\x00', direction='right')
        >>> p.build(b'foo')
        b'foo\x00\x00\x00'
        >>> p.parse(b'bar\x00\x00\x00')
        b'bar'
        >>> p.sizeof()
        6
        >>> p.parse(b'baz')
        Traceback (most recent call last):
        ...
        structures.ParsingError: could not read enough bytes, expected 6, found 3

        >>> p_left = Padded(Bytes(3), 6, padchar=b'X', direction='left')
        >>> p_left.build(b'bar')
        b'XXXbar'
        >>> p_left.parse(b'XXXabc')
        b'abc'

        >>> p_center = Padded(Bytes(3), 6, padchar=b'Y', direction='center')
        >>> p_center.build(b'baz')
        b'YbazYY'
        >>> p_center.parse(b'YYdefY')
        b'def'

    Providing invalid parameters results in a ValueError:

        >>> Padded(Bytes(3), -2)
        Traceback (most recent call last):
        ...
        ValueError: length must be >= 0, got -2
        >>> Padded(Bytes(3), 4, padchar=b'\x00\x00')
        Traceback (most recent call last):
        ...
        ValueError: padchar must be a single-length bytes, got b'\x00\x00'
        >>> Padded(Bytes(3), 4, direction='up')
        Traceback (most recent call last):
        ...
        ValueError: direction must be 'right', 'left', or 'center', got 'up'

    :param construct: A construct to be padded.

    :param length: Pad to achieve exactly this number of bytes.

    :param padchar: Pad using this char. Default is b'\x00' (zero byte).

    :param direction: Pad in this direction. Must be 'right', 'left', or
    'center'. Default is 'right'.

    """
    __slots__ = Subconstruct.__slots__ + ('length', 'padchar', 'direction')

    def __init__(self, construct: Construct, length: int, padchar=b'\x00',
                 direction='right'):
        super().__init__(construct)
        if length < 0:
            raise ValueError('length must be >= 0, got {}'.format(length))
        self.length = length
        if len(padchar) != 1:
            raise ValueError('padchar must be a single-length bytes, '
                             'got {!r}'.format(padchar))
        self.padchar = padchar
        if direction not in {'right', 'left', 'center'}:
            raise ValueError("direction must be 'right', 'left', or 'center', "
                             'got {!r}'.format(direction))
        self.direction = direction

    def _build_stream(self, obj, stream, context):
        stream2 = BytesIO()
        ctx_value = self.construct._build_stream(obj, stream2, context)
        data = stream2.getvalue()
        if self.direction == 'left':
            data = data.rjust(self.length, self.padchar)
        elif self.direction == 'right':
            data = data.ljust(self.length, self.padchar)
        elif self.direction == 'center':
            data = data.center(self.length, self.padchar)
        stream.write(data)
        return ctx_value

    def _parse_stream(self, stream, context):
        data = stream.read(self.length)
        if len(data) != self.length:
            raise ParsingError(
                'could not read enough bytes, expected {}, found {}'.format(
                    self.length, len(data)
                )
            )
        if self.direction == 'right':
            data = data.rstrip(self.padchar)
        elif self.direction == 'left':
            data = data.lstrip(self.padchar)
        elif self.direction == 'center':
            data = data.strip(self.padchar)
        return self.construct._parse_stream(BytesIO(data), context)

    def _sizeof(self, context):
        return self.length

    def _repr(self):
        return 'Padded({}, length={}, padchar={!r}, direction={!r})'.format(
            self.construct, self.length, self.padchar, self.direction
        )


class Aligned(Padded):
    r"""
    Appends additional null bytes to achieve a length that is
    shortest multiple of a length.

        >>> a = Aligned(Bytes(1)[2:8], 4)
        >>> a
        Aligned(Repeat(Bytes(1), start=2, stop=8), length=4, padchar=b'\x00', direction='right')
        >>> a.build(b'foobar')
        b'foobar\x00\x00'
        >>> b''.join(a.parse(b'foo\x00'))
        b'foo\x00'
        >>> a.sizeof()
        Traceback (most recent call last):
        ...
        structures.SizeofError: cannot determine size of variable sized Repeat

        >>> a = Aligned(Bytes(6), 4)
        >>> a.sizeof()
        8
        >>> a.parse(b'foobar\x00\x01')
        Traceback (most recent call last):
        ...
        structures.ParsingError: must read padding of b'\x00\x00', got b'\x00\x01'

    Parameters are the same as ``Padded``.

    """
    __slots__ = Padded.__slots__

    def _build_stream(self, obj, stream, context):
        before = stream.tell()
        ctx_value = self.construct._build_stream(obj, stream, context)
        after = stream.tell()
        padlen = -(after - before) % self.length
        stream.write(self.padchar * padlen)
        return ctx_value

    def _parse_stream(self, stream, context):
        before = stream.tell()
        obj = self.construct._parse_stream(stream, context)
        after = stream.tell()
        padlen = -(after - before) % self.length
        padding = stream.read(padlen)
        if padding != self.padchar * padlen:
            raise ParsingError(
                'must read padding of {!r}, got {!r}'.format(
                    self.padchar * padlen, padding,
                )
            )
        return obj

    def _sizeof(self, context):
        size = self.construct._sizeof(context)
        return size + (-size % self.length)

    def _repr(self):
        return 'Aligned({}, length={}, padchar={!r}, direction={!r})'.format(
            self.construct, self.length, self.padchar, self.direction
        )


# Strings
class StringEncoded(Adapted):
    """
    Helper adapter for strings, to encode before building and decode
    after parsing with the specified encoding.

        >>> e = StringEncoded(Bytes(3), 'utf-8')
        >>> e
        StringEncoded(Bytes(3), encoding='utf-8')
        >>> e.build('foo')
        b'foo'
        >>> e.parse(b'bar')
        'bar'
        >>> e.sizeof()
        3

    If no encoding specified, no encoding/decoding happens.

        >>> e = StringEncoded(Bytes(3))
        >>> e
        StringEncoded(Bytes(3))
        >>> e.build(b'foo')
        b'foo'
        >>> e.parse(b'bar')
        b'bar'
        >>> # Python3.4 and pypy3 error with
        >>> # 'str' does not support the buffer interface
        >>> # Python3.5+ errors with
        >>> # a bytes-like object is required, not 'str'
        >>> e.build('baz')
        Traceback (most recent call last):
        ...
        structures.BuildingError: ...

    :param construct: Construct to adapt with encoding/decoding.

    :param encoding: Encode/decode using this encoding. Default is None,
    meaning no encoding/decoding happens.

    """

    __slots__ = Adapted.__slots__ + ('encoding',)

    def __init__(self, construct: Construct, encoding=None):
        encode = decode = None
        if encoding is not None:
            def encode(obj):
                return obj.encode(encoding)

            def decode(obj):
                return obj.decode(encoding)

        super().__init__(construct, before_build=encode, after_parse=decode)
        self.encoding = encoding

    def _repr(self):
        if self.encoding is None:
            return 'StringEncoded({})'.format(self.construct)
        return 'StringEncoded({}, encoding={!r})'.format(
            self.construct, self.encoding
        )


class String(Subconstruct):
    r"""
    String constrained only by the specified constant length.
    Null bytes are padded/trimmed from the left or right side.

        >>> s = String(8, encoding='utf-8')
        >>> s
        String(8, encoding='utf-8', padchar=b'\x00', direction='right')
        >>> s.build('foo')
        b'foo\x00\x00\x00\x00\x00'
        >>> s.parse(b'foo\x00\x00\x00\x00\x00')
        'foo'
        >>> s.sizeof()
        8

    Longer strings are not supported:

        >>> s.build('foobarbazxxxyyy')
        Traceback (most recent call last):
        ...
        structures.BuildingError: length of the object to build must be in range [1, 9), got 15

    But you can slice the data in advance:

        >>> a = Adapted(s, before_build=lambda obj: obj[:8])
        >>> a.build('foobarbazxxxyyy')
        b'foobarba'

    Encoding can be omitted, in that case ``String`` builds and
    parses from bytes, not strings:

        >>> s = String(8)
        >>> s.build(b'foo')
        b'foo\x00\x00\x00\x00\x00'
        >>> s.parse(b'foo\x00\x00\x00\x00\x00')
        b'foo'

    ``padchar`` and ``direction`` examples can be found in ``Padded`` docstring.

    :param length: Number of bytes taken by the string. Not that the actual
    string can be less than this number. In that case the string will be
    padded according to ``padchar`` and ``paddir``.

    :param encoding: See ``StringEncoded``.

    :param padchar: See ``Padded``.

    :param direction: See ``Padded``.

    """
    __slots__ = Subconstruct.__slots__ + ('length',)

    def __init__(self, length: int, encoding: str = None, padchar=b'\x00',
                 direction='right'):
        variable_bytes = Adapted(
            Bytes(1)[1:length + 1], after_parse=b''.join,
        )
        construct = Padded(variable_bytes, length, padchar, direction)
        super().__init__(StringEncoded(construct, encoding))
        self.length = length

    def _repr(self):
        encoded = self.construct  # type: StringEncoded
        padded = self.construct.construct  # type: Padded
        fields = [str(self.length)]
        if encoded.encoding is not None:
            fields.append('encoding={!r}'.format(encoded.encoding))
        fields += [
            'padchar={!r}'.format(padded.padchar),
            'direction={!r}'.format(padded.direction),
        ]
        return 'String({})'.format(', '.join(fields))


class PascalString(Subconstruct):
    r"""
    Length-prefixed string.

        >>> p = PascalString(Integer(1), encoding='utf-8')
        >>> p
        PascalString(length_field=Integer(1, byteorder='big', signed=False), encoding='utf-8')
        >>> p.build('foo')
        b'\x03foo'
        >>> p.parse(b'\x08\xd0\x98\xd0\xb2\xd0\xb0\xd0\xbd')
        'Иван'
        >>> p.sizeof()
        Traceback (most recent call last):
        ...
        structures.SizeofError: PascalString has no fixed size

    Encoding can be omitted, in that case ``PascalString`` builds and
    parses from bytes, not strings:

        >>> p = PascalString(Integer(1))
        >>> p
        PascalString(length_field=Integer(1, byteorder='big', signed=False))
        >>> p.build(b'foo')
        b'\x03foo'
        >>> p.parse(b'\x06foobar')
        b'foobar'

    :param length_field: Construct used to build/parse the length.

    :param encoding: See ``StringEncoded``.

    """
    __slots__ = Subconstruct.__slots__

    def __init__(self, length_field: Construct, encoding: str = None):
        super().__init__(StringEncoded(
            Prefixed(Bytes(), length_field),
            encoding,
        ))

    def _sizeof(self, context):
        raise SizeofError('PascalString has no fixed size')

    def _repr(self):
        encoding = self.construct.encoding
        length_field = self.construct.construct.length_field
        if encoding is None:
            return 'PascalString(length_field={})'.format(length_field)
        return 'PascalString(length_field={}, encoding={!r})'.format(
            length_field, encoding,
        )


class CString(Subconstruct):
    r"""
    String ending in a zero byte.

        >>> s = CString('utf-8')
        >>> s
        CString(encoding='utf-8')
        >>> s.build('foo')
        b'foo\x00'
        >>> s.parse(b'bar\x00baz')
        'bar'
        >>> s.sizeof()
        Traceback (most recent call last):
        ...
        structures.SizeofError: CString has no fixed size

    You can omit encoding to build/parse raw bytes:

        >>> s = CString()
        >>> s
        CString()
        >>> s.build(b'foo')
        b'foo\x00'
        >>> s.parse(b'bar\x00')
        b'bar'

    Note that it is not safe to specify multibyte encodings allowing null byte
    in arbitrary code points like UTF16 or UTF32.

        >>> s = CString('utf-16-le')
        >>> s.build('foo')
        b'f\x00o\x00o\x00\x00'
        >>> s.parse(_)
        Traceback (most recent call last):
        ...
        structures.ParsingError: 'utf...' codec can't decode byte 0x66 in position 0: truncated data

    :param encoding: See ``StringEncoded``.

    """
    __slots__ = Subconstruct.__slots__

    def __init__(self, encoding: str = None):
        construct = Adapted(
            Repeat(
                Bytes(1), start=0, stop=sys.maxsize,
                until=lambda items: items[-1] == b'\x00',
            ),
            before_build=lambda obj: obj + b'\x00',
            after_parse=lambda obj: b''.join(obj[:-1]),
        )
        super().__init__(StringEncoded(construct, encoding))

    def _sizeof(self, context):
        raise SizeofError('CString has no fixed size')

    def _repr(self):
        if self.construct.encoding is not None:
            return 'CString(encoding={!r})'.format(self.construct.encoding)
        return 'CString()'


class Line(Subconstruct):
    r"""
    String ending in CRLF (b'\r\n'). Useful for building and parsing
    text-based network protocols.

        >>> l = Line()
        >>> l
        Line()
        >>> l.build('foo')
        b'foo\r\n'
        >>> l.parse(b'bar\r\n')
        'bar'
        >>> l.sizeof()
        Traceback (most recent call last):
        ...
        structures.SizeofError: Line has no fixed size

    Default encoding is latin-1, but encoding/decoding can be disabled. In
    that case it's up to the application to decide how to process these bytes.

        >>> l = Line(raw=True)
        >>> l
        Line(raw=True)
        >>> l.build(b'foo')
        b'foo\r\n'
        >>> l.parse(_)
        b'foo'
        >>> l.parse(b'bar\r\nbaz\r\n')
        b'bar'

    :param raw: If True, no latin-1 encoding/decoding happens.

    """
    __slots__ = Subconstruct.__slots__ + ('raw',)

    def __init__(self, raw=False):
        construct = Adapted(
            Repeat(
                Bytes(1), start=0, stop=sys.maxsize,
                until=lambda items: items[-2:] == [b'\r', b'\n'],
            ),
            before_build=lambda obj: obj + b'\r\n',
            after_parse=lambda obj: b''.join(obj[:-2]),
        )
        if not raw:
            construct = StringEncoded(construct, 'latin-1')
        super().__init__(construct)
        self.raw = raw

    def _sizeof(self, context):
        raise SizeofError('Line has no fixed size')

    def _repr(self):
        if self.raw:
            return 'Line(raw=True)'
        return 'Line()'


# Structs.
class StructMeta(type):
    """
    Metaclass for Struct, a mandatory machinery to maintain an ordered
    class namespace and __slots__.
    """

    if not CLASS_NAMESPACE_ORDERED:  # pragma: nocover
        @classmethod
        def __prepare__(mcs, name, bases):
            return OrderedDict()

    def __new__(mcs, name, bases, namespace):
        fields = OrderedDict([
            (key, value) for key, value in namespace.items()
            if isinstance(value, Construct)
        ])
        namespace['__struct_fields__'] = fields
        slots = namespace.get('__slots__')
        if slots is None:
            # Make sure user defined structs aren't eating memory.
            namespace['__slots__'] = Construct.__slots__
        return type.__new__(mcs, name, bases, namespace)


class Struct(Construct, metaclass=StructMeta):
    r"""
    Sequence of named constructs, similar to structs in C.
    The elements are parsed and built in the order they are defined.

    Size is the sum of all construct sizes, unless some construct raises
    SizeofError.

        >>> class Entry(Struct):
        ...     key = Integer(1)
        ...     value = Bytes(3)
        >>> entry = Entry()
        >>> entry
        Entry()
        >>> entry.build({'key': 1, 'value': b'foo'})
        b'\x01foo'
        >>> entry.parse(b'\x10bar') == {'key': 16, 'value': b'bar'}
        True
        >>> entry.sizeof()
        4

    Struct fields can be inspected using ``fields`` property:

        >>> entry.fields
        OrderedDict([('key', Integer(1, byteorder='big', signed=False)), ('value', Bytes(3))])

    What makes structs special is that during building/parsing they
    fill in the building/parsing context with values to build/parsed values
    which allows to use Contextual construct to make some struct fields
    dependent of another:

        >>> class Entry(Struct):
        ...     length = Integer(1)
        ...     data = Contextual(Bytes, lambda ctx: ctx['length'])
        >>> entry = Entry()
        >>> entry.build({'length': 3, 'data': b'foo'})
        b'\x03foo'
        >>> entry.build({'length': 6, 'data': b'abcdef'})
        b'\x06abcdef'
        >>> entry.parse(b'\x02barbaz') == {'length': 2, 'data': b'ba'}
        True
        >>> entry.sizeof(context={'length': 10})
        11

    Structs can be composed:

        >>> class Header(Struct):
        ...     payload_size = Integer(1)
        >>> class Message(Struct):
        ...     header = Header()
        ...     payload = Contextual(Bytes, lambda ctx: ctx['header']['payload_size'])
        >>> message = Message()
        >>> data = {'header': {'payload_size': 3}, 'payload': b'foo'}
        >>> message.build(data)
        b'\x03foo'
        >>> message.parse(_) == data
        True

    Structs can be embedded, in this case the embedded struct works with the
    "outer" context instead of creating a new one:

        >>> class Header(Struct):
        ...     payload_size = Integer(1)
        >>> class Message(Struct):
        ...     header = Header(embedded=True)
        ...     payload = Contextual(Bytes, lambda ctx: ctx['payload_size'])
        >>> message = Message()
        >>> data = {'payload_size': 3, 'payload': b'foo'}
        >>> message.build(data)
        b'\x03foo'
        >>> message.parse(_) == data
        True

    Embedded property is preserved when an embedded struct is wrapped into
    other constructs (like Adapted):

        >>> class Header(Struct):
        ...     payload_size = Integer(1)
        >>> def mul_by_3(obj):
        ...     obj['payload_size'] *= 3
        ...     return obj
        >>> class Message(Struct):
        ...     header = Adapted(
        ...         Header(embedded=True),
        ...         before_build=mul_by_3,
        ...         after_parse=mul_by_3,
        ...     )
        ...     payload = Contextual(Bytes, lambda ctx: ctx['payload_size'])
        >>> message = Message()
        >>> message.build({'payload_size': 1, 'payload': b'foo'})
        b'\x03foo'
        >>> message.parse(b'\x01bar') == {'payload_size': 3, 'payload': b'bar'}
        True

    :param embedded: If True, this struct will be embedded into another struct.

    """

    def __init__(self, *, embedded=False):
        super().__init__()
        self._embedded = embedded

    @property
    def fields(self):
        return self.__struct_fields__  # noqa

    def _build_stream(self, obj, stream, context):
        if not self._embedded:
            context = context.new_child(obj)
        for name, field in self.fields.items():
            if not field._embedded:
                subobj = obj.get(name)
            else:
                subobj = obj
            ctx_value = field._build_stream(subobj, stream, context)
            if ctx_value is not None:
                context[name] = ctx_value

    def _parse_stream(self, stream, context):
        if not self._embedded:
            context = context.new_child()
        obj = {}
        for name, field in self.fields.items():
            subobj = field._parse_stream(stream, context)
            if not field._embedded:
                context[name] = obj[name] = subobj
            else:
                obj.update(subobj)
                context.update(subobj)
        return obj

    def _sizeof(self, context):
        return sum(field._sizeof(context) for field in self.fields.values())

    def _repr(self):
        return '{}({})'.format(
            self.__class__.__name__, 'embedded=True' if self._embedded else '',
        )


class Contextual(Construct):
    r"""
    Construct that makes other construct dependent of the context.
    Useful in structs.

        >>> c = Contextual(Integer, lambda ctx: (ctx['length'], 'big'))
        >>> c
        Contextual(Integer, <function <lambda> at ...>)
        >>> c.build(1, context={'length': 1})
        b'\x01'
        >>> c.build(1, context={'length': 2})
        b'\x00\x01'
        >>> c.build(1)
        Traceback (most recent call last):
        ...
        structures.ContextualError: 'length'
        >>> c.parse(b'\x00')
        Traceback (most recent call last):
        ...
        structures.ContextualError: 'length'
        >>> c.sizeof(context={'length': 4})
        4
        >>> c.sizeof()
        Traceback (most recent call last):
        ...
        structures.ContextualError: 'length'

    :param to_construct: Construct subclass to be instantiated during
    building/parsing.

    :param *args_funcs: Functions of context (or constant values) to be
    called during building/parsing, returned values form positional arguments
    to be passed to ``to_construct`` class.

    :param **kwargs_funcs: Functions of context (or constant values) to be
    called during building/parsing, returned values form keyword arguments
    to be passed to ``to_construct`` class.

    """
    __slots__ = Construct.__slots__ + ('to_construct', 'args_func')

    def __init__(self, to_construct, args_func):
        super().__init__()
        self.to_construct = to_construct
        self.args_func = args_func

    def _build_stream(self, obj, stream, context):
        try:
            args = self.args_func(context)
        except Exception as exc:
            raise ContextualError(str(exc))
        if not isinstance(args, (list, tuple)):
            args = [args]
        construct = self.to_construct(*args)
        return construct._build_stream(obj, stream, context)

    def _parse_stream(self, stream, context):
        try:
            args = self.args_func(context)
        except Exception as exc:
            raise ContextualError(str(exc))
        if not isinstance(args, (list, tuple)):
            args = [args]
        construct = self.to_construct(*args)
        return construct._parse_stream(stream, context)

    def _sizeof(self, context):
        try:
            args = self.args_func(context)
        except Exception as exc:
            raise ContextualError(str(exc))
        if not isinstance(args, (list, tuple)):
            args = [args]
        construct = self.to_construct(*args)
        return construct._sizeof(context)

    def _repr(self):
        return 'Contextual({}, {})'.format(
            self.to_construct.__name__,
            self.args_func,
        )


class Computed(Construct):
    r"""
    Computed fields do not participate in building, but return computed values
    when parsing and populate the context with computed values:

        >>> class Example(Struct):
        ...     x = Integer(1)
        ...     y = Integer(1)
        ...     x_plus_y = Computed(lambda ctx: ctx['x'] + ctx['y'])
        ...     z = Contextual(Bytes, lambda ctx: ctx['x_plus_y'])
        >>> example = Example()
        >>> example.parse(b'\x01\x02foo') == {'x': 1, 'y': 2, 'z': b'foo', 'x_plus_y': 3}
        True

        >>> c = Computed(b'foo')
        >>> c
        Computed(b'foo')
        >>> c.sizeof()
        0

    :param value: Computed value. A function of context can be specified
    to compute values dynamically.

    """
    __slots__ = Construct.__slots__ + ('value',)

    def __init__(self, value):
        super().__init__()
        self.value = value

    def _build_stream(self, obj, stream, context):
        if obj is None:
            obj = self.value(context) if callable(self.value) else self.value
        return obj

    def _parse_stream(self, stream, context):
        return self.value(context) if callable(self.value) else self.value

    def _sizeof(self, context):
        return 0

    def _repr(self):
        return 'Computed({!r})'.format(self.value)


class BitFields(Construct):
    r"""
    Build and parse named bit-wise fields. Values are always built from
    unsigned big-byteorder integers and parsed as unsigned
    big-byteorder integers.

        >>> b = BitFields('version:4, header_length:4')
        >>> b
        BitFields('version:4, header_length:4')
        >>> b.build({'version': 4, 'header_length': 0})
        b'@'
        >>> b.parse(b'\x00') == {'version': 0, 'header_length': 0}
        True
        >>> b.sizeof()
        1

    Fields can span over 8 bits, and the whole construct is byte-aligned
    (i.e. it will read as many bytes as needed and ignore trailing bits that
    do not have definitions in the spec):

        >>> b = BitFields('foo:12,bar:5')
        >>> b.sizeof()
        3
        >>> b.build({'foo': 4095, 'bar': 31})
        b'\xff\xff\x80'
        >>> b.parse(b'\x09\x11\x00') == {'foo': 145, 'bar': 2}
        True

    You can omit any field during building, in that case 0 will be built.
    That allows to emulate padding that comes before actual data:

        >>> b = BitFields('padding:7, flag:1')
        >>> b.parse(b'\x01') == {'padding': 0, 'flag': 1}
        True
        >>> b.build({'flag': 0})
        b'\x00'

    If you try to build from integer that can't be packed into the specified
    amount of bits, a BuildingError will be raised:

        >>> b.build({'flag': 10})
        Traceback (most recent call last):
        ...
        structures.BuildingError: cannot pack 10 into 1 bit

    Of course, fields bit length must be >=0:

        >>> BitFields('foo:-5')
        Traceback (most recent call last):
        ...
        ValueError: 'foo' bit length must be >= 0, got -5

    You can also embed BitFields into a struct:

        >>> class Entry(Struct):
        ...     header = BitFields('foo:2,bar:2,length:4', embedded=True)
        ...     payload = Contextual(Bytes, lambda ctx: ctx['length'])
        >>> entry = Entry()
        >>> entry.build({'foo': 2, 'bar': 0, 'length': 3, 'payload': b'baz'})
        b'\x83baz'
        >>> entry.parse(b'\x33xxx') == {
        ...     'foo': 0, 'bar': 3, 'length': 3, 'payload': b'xxx'
        ... }
        True

    :param spec: Fields definition, a comma separated list of
    name:length-in-bits pairs. Spaces between commas are allowed.

    :param embedded: If True, this construct will be embedded into the
    enclosed struct.

    """
    __slots__ = Construct.__slots__ + ('spec', 'fields', '_length')

    def __init__(self, spec, embedded=False):
        super().__init__()
        self.spec = spec
        self._embedded = embedded
        self.fields = OrderedDict()
        for field in map(str.strip, spec.split(',')):
            name, length = field.split(':')
            self.fields[name] = length = int(length)
            if length < 0:
                raise ValueError('{!r} bit length must be >= 0, got {}'.format(
                    name, length
                ))
        self._length = ceil(
            sum(length for _, length in self.fields.items()) / 8
        )

    def _build_stream(self, obj, stream, context):
        bits = []
        for name, length in self.fields.items():
            subobj = obj.get(name, 0)
            bin_subobj = bin(subobj)[2:].rjust(length, '0')
            if len(bin_subobj) != length:
                raise BuildingError('cannot pack {} into {} bit{}'.format(
                    subobj, length, 's' if length > 1 else ''
                ))
            bits += bin_subobj
        data = []
        bits = ''.join(bits).ljust(self._length * 8, '0')
        for idx in range(self._length):
            part = bits[idx * 8:(idx + 1) * 8]
            data.append(int(part, 2))
        stream.write(bytes(data))

    def _parse_stream(self, stream, context):
        data = stream.read(self._length)
        bits = ''.join(bin(byte)[2:].rjust(8, '0') for byte in data)
        obj = {}
        idx = 0
        for name, length in self.fields.items():
            obj[name] = int(bits[idx:idx + length], 2)
            idx += length
        return obj

    def _sizeof(self, context):
        return self._length

    def _repr(self):
        return 'BitFields({!r})'.format(self.spec)


# Conditionals
class Const(Subconstruct):
    r"""
    Build and parse constant values using the given construct.
    ``None`` can be specified for building.

        >>> c = Const(Flag(), True)
        >>> c
        Const(Flag(), value=True)
        >>> c.build(True)
        b'\x01'
        >>> c.build(None)
        b'\x01'
        >>> c.build(False)
        Traceback (most recent call last):
        ...
        structures.BuildingError: provided value must be None or True, got False
        >>> c.parse(b'\x01')
        True
        >>> c.parse(b'\x00')
        Traceback (most recent call last):
        ...
        structures.ParsingError: parsed value must be True, got False

    Since the majority of constant fields are ASCII signatures, ``Const``
    supports the following short-hand:

        >>> c = Const(b'SIGNATURE')
        >>> c.build(None)
        b'SIGNATURE'
        >>> c.parse(b'SIGNATURE')
        b'SIGNATURE'
        >>> c
        Const(Bytes(9), value=b'SIGNATURE')

    :param construct: Construct used to build and parse the constant value.

    :param value: Constant value to be built and parsed.

    """
    __slots__ = Subconstruct.__slots__ + ('value',)

    def __init__(self, construct, value=None):
        if value is None:
            if isinstance(construct, bytes):
                # Handle the simplest Const(b'foobar') case
                construct, value = Bytes(len(construct)), construct
        super().__init__(construct)
        self.value = value

    def _build_stream(self, obj, stream, context):
        if obj not in (None, self.value):
            raise BuildingError('provided value must be None '
                                'or {!r}, got {!r}'.format(self.value, obj))
        return self.construct._build_stream(self.value, stream, context)

    def _parse_stream(self, stream, context):
        obj = self.construct._parse_stream(stream, context)
        if obj != self.value:
            raise ParsingError('parsed value must be '
                               '{!r}, got {!r}'.format(self.value, obj))
        return obj

    def _repr(self):
        return 'Const({}, value={!r})'.format(
            self.construct, self.value
        )


class Raise(Construct):
    """
    Construct that unconditionally raises BuildingError when building,
    ParsingError when parsing and SizeofError when calculating the size
    with the given message.
    Useful in conditional constructs (Enum, Switch, If, etc).

        >>> r = Raise('a condition is false')
        >>> r
        Raise(message='a condition is false')
        >>> r.build(None)
        Traceback (most recent call last):
        ...
        structures.BuildingError: a condition is false
        >>> r.parse(b'anything')
        Traceback (most recent call last):
        ...
        structures.ParsingError: a condition is false
        >>> r.sizeof()
        Traceback (most recent call last):
        ...
        structures.SizeofError: a condition is false

    :param message: Message to be shown when raising the errors. Use
    ``Contextual`` construct to specify dynamic messages.

    """
    __slots__ = Construct.__slots__ + ('message',)

    def __init__(self, message):
        super().__init__()
        self.message = message

    def _build_stream(self, obj, stream, context):
        raise BuildingError(self.message)

    def _parse_stream(self, stream, context):
        raise ParsingError(self.message)

    def _sizeof(self, context):
        raise SizeofError(self.message)

    def _repr(self):
        return 'Raise(message={!r})'.format(self.message)


class If(Construct):
    r"""
    A conditional building and parsing of a construct depending
    on the predicate.

        >>> i = If(lambda ctx: ctx['flag'], Const(b'True'), Const(b'False'))
        >>> i
        If(<function <lambda> at ...>, then_construct=Const(Bytes(4), value=b'True'), else_construct=Const(Bytes(5), value=b'False'))
        >>> i.build(None, context={'flag': True})
        b'True'
        >>> i.build(None, context={'flag': False})
        b'False'
        >>> i.parse(b'True', context={'flag': True})
        b'True'
        >>> i.parse(b'False', context={'flag': False})
        b'False'
        >>> i.sizeof(context={'flag': True})
        4
        >>> i.sizeof(context={'flag': False})
        5

    An else clause can be omitted, Pass() will be used:

        >>> i = If(lambda ctx: ctx['flag'], Const(b'True'))
        >>> i
        If(<function <lambda> at ...>, Const(Bytes(4), value=b'True'))
        >>> i.sizeof(context={'flag': True})
        4
        >>> i.sizeof(context={'flag': False})
        0

    :param predicate: Function of context called during building/parsing/sizeof
    calculation. If the returned value is True, ``then_construct`` is used.
    Otherwise ``else_construct`` is used.

    :param then_construct: Positive branch construct.

    :param else_construct: Negative branch construct.

    """
    __slots__ = Construct.__slots__ + ('predicate', 'then_construct',
                                       'else_construct')

    def __init__(self, predicate, then_construct, else_construct=Pass()):
        super().__init__()
        self.predicate = predicate
        self.then_construct = then_construct
        self.else_construct = else_construct

    def _build_stream(self, obj, stream, context):
        if self.predicate(context):
            construct = self.then_construct
        else:
            construct = self.else_construct
        return construct._build_stream(obj, stream, context)

    def _parse_stream(self, stream, context):
        if self.predicate(context):
            construct = self.then_construct
        else:
            construct = self.else_construct
        return construct._parse_stream(stream, context)

    def _sizeof(self, context):
        if self.predicate(context):
            construct = self.then_construct
        else:
            construct = self.else_construct
        return construct._sizeof(context)

    def _repr(self):
        if isinstance(self.else_construct, Pass):
            return 'If({}, {})'.format(self.predicate, self.then_construct)
        return 'If({}, then_construct={!r}, else_construct={!r})'.format(
            self.predicate, self.then_construct, self.else_construct,
        )


class Switch(Construct):
    r"""
    Construct similar to switches in C.
    Conditionally build and parse bytes depending on the key function.

        >>> s = Switch(
        ...     lambda ctx: ctx['foo'],
        ...     cases={1: Integer(1), 2: Bytes(3)}
        ... )
        >>> s
        Switch(<function <lambda> ...>, cases={1: Integer(...), 2: Bytes(3)})
        >>> s.build(5, context={'foo': 1})
        b'\x05'
        >>> s.build(b'bar', context={'foo': 2})
        b'bar'
        >>> s.parse(b'baz', context={'foo': 2})
        b'baz'
        >>> s.sizeof(context={'foo': 2})
        3
        >>> s.build(b'baz', context={'foo': 3})
        Traceback (most recent call last):
        ...
        structures.BuildingError: no default case specified
        >>> s.parse(b'baz', context={'foo': 3})
        Traceback (most recent call last):
        ...
        structures.ParsingError: no default case specified

    You can choose how to process missing cases error by providing default case:

        >>> s = Switch(lambda ctx: None, cases={}, default=Pass())
        >>> s
        Switch(<function <lambda> ...>, cases={}, default=Pass())
        >>> s.build(None)
        b''
        >>> s.parse(b'') is None
        True

    :param key: Function of context, used to determine the appropriate case
    to build/parse/calculate sizeof.

    :param cases: Mapping between cases and constructs to build/parse/calculate
    sizeof.

    :param default: Construct used when the key is not found in cases.
    Default is Raise().

    """
    __slots__ = Construct.__slots__ + ('key', 'cases', 'default')

    def __init__(self, key, cases, default=None):
        super().__init__()
        self.key = key
        self.cases = cases
        if default is None:
            default = Raise('no default case specified')
        self.default = default

    def _build_stream(self, obj, stream, context):
        construct = self.cases.get(self.key(context), self.default)
        return construct._build_stream(obj, stream, context)

    def _parse_stream(self, stream, context):
        construct = self.cases.get(self.key(context), self.default)
        return construct._parse_stream(stream, context)

    def _sizeof(self, context):
        construct = self.cases.get(self.key(context), self.default)
        return construct._sizeof(context)

    def _repr(self):
        if isinstance(self.default, Raise):
            return 'Switch({}, cases={})'.format(self.key, self.cases)
        return 'Switch({}, cases={}, default={})'.format(
            self.key, self.cases, self.default,
        )


class Enum(Subconstruct):
    r"""
    Like a built-in ``Enum`` class, maps string names to values.

        >>> e = Enum(Flag(), cases={'yes': True, 'no': False})
        >>> # Another python 3.4 only glitch, can't rely on any specific dict order
        >>> e
        Enum(Flag(), cases={...})
        >>> e.build('yes')
        b'\x01'
        >>> e.parse(b'\x00')
        'no'
        >>> e.sizeof()
        1

    Unexpected names result in error:

        >>> e = Enum(Bytes(3), cases={'x': b'xxx', 'y': b'yyy'})
        >>> e.build('z')
        Traceback (most recent call last):
        ...
        structures.BuildingError: no default case specified
        >>> e.parse(b'zzz')
        Traceback (most recent call last):
        ...
        structures.ParsingError: no default case specified

    You can choose how to process missing cases error by providing default case:

        >>> e = Enum(Bytes(3), cases={'x': b'xxx', 'y': b'yyy'}, default=Pass())
        >>> e
        Enum(Bytes(3), cases={...}, default=Pass())
        >>> e.build('z')
        b''
        >>> e.parse(b'z') is None
        True

    During building, even if a value is provided instead of a name, an enum
    will populate context with the name, not with the value.

        >>> class Entry(Struct):
        ...     foo = Enum(Flag(), cases={'yes': True, 'no': False})
        ...     bar = Computed(lambda ctx: print('In context:', ctx['foo']))
        >>> Entry().build({'foo': True})
        In context: yes
        b'\x01'

    :param construct: Construct used to build/parse/calculate sizeof.

    :param cases: Mapping between names and values.

    :param default: Construct used when the name is not found in cases.
    Default is Raise().

    """
    __slots__ = Subconstruct.__slots__ + ('cases', 'build_cases',
                                          'parse_cases', 'default')

    def __init__(self, construct, cases, default=None):
        super().__init__(construct)
        # For building we need k -> v and v -> v mapping
        self.cases = cases.copy()
        self.build_cases = cases.copy()
        self.build_cases.update({v: v for v in cases.values()})
        # For parsing we need v -> k mapping
        self.parse_cases = {v: k for k, v in cases.items()}
        if default is None:
            default = Raise('no default case specified')
        self.default = default

    def _build_stream(self, obj, stream, context):
        try:
            obj2 = self.build_cases[obj]
        except KeyError:
            return self.default._build_stream(obj, stream, context)
        fallback = stream.tell()
        try:
            self.construct._build_stream(obj2, stream, context)
        except BuildingError:
            stream.seek(fallback)
            self.default._build_stream(obj2, stream, context)
        # always put in context the name, not value
        return self.parse_cases[obj2]

    def _parse_stream(self, stream, context):
        fallback = stream.tell()
        try:
            obj = self.construct._parse_stream(stream, context)
        except ParsingError:
            stream.seek(fallback)
            return self.default._parse_stream(stream, context)
        try:
            obj = self.parse_cases[obj]
        except KeyError:
            stream.seek(fallback)
            return self.default._parse_stream(stream, context)
        return obj

    def _repr(self):
        if isinstance(self.default, Raise):
            return 'Enum({}, cases={})'.format(
                self.construct, self.cases
            )
        return 'Enum({}, cases={}, default={})'.format(
            self.construct, self.cases, self.default,
        )


# Stream manipulation and inspection
class Offset(Subconstruct):
    r"""
    Changes the stream to a given offset where building or parsing
    should take place, and restores the stream position when finished.
    Mostly useful in structs.

        >>> o = Offset(Bytes(1), 4)
        >>> o
        Offset(Bytes(1), offset=4)
        >>> o.parse(b'abcdef')
        b'e'
        >>> o.build(b'Z')
        b'\x00\x00\x00\x00Z'
        >>> o.sizeof()
        1

    Providing invalid parameters results in a ValueError:

        >>> Offset(Bytes(1), -2)
        Traceback (most recent call last):
        ...
        ValueError: offset must be >= 0, got -2

    Size is defined by the size of the provided construct, although it may
    seem that building/parsing do not consume this exact number of bytes.
    The reason why size is defined like that is that the primary use-case
    for ``Offset`` is to support building/parsing of formats like ELF32
    when the payload comes after a variable-sized header, and its position
    and length are defined in the first section of the header.

    :param construct: Construct to build/parse/calculate sizeof at the given
    offset.

    :param offset: Offset to seek the stream to (from the current position).

    """
    __slots__ = Subconstruct.__slots__ + ('offset',)

    def __init__(self, construct, offset):
        super().__init__(construct)
        if offset < 0:
            raise ValueError('offset must be >= 0, got {}'.format(offset))
        self.offset = offset

    def _build_stream(self, obj, stream, context):
        fallback = stream.tell()
        stream.seek(self.offset)
        ctx_value = self.construct._build_stream(obj, stream, context)
        stream.seek(fallback)
        return ctx_value

    def _parse_stream(self, stream, context):
        fallback = stream.tell()
        stream.seek(self.offset)
        obj = self.construct._parse_stream(stream, context)
        stream.seek(fallback)
        return obj

    def _repr(self):
        return 'Offset({}, offset={})'.format(
            self.construct, self.offset,
        )


class Tell(Construct):
    r"""
    Gets the stream position when building or parsing.
    Tell is useful for adjusting relative offsets to absolute positions,
    or to measure sizes of Constructs. To get an absolute pointer,
    use a Tell plus a relative offset. To get a size, place two Tells
    and measure their difference using a Contextual field.
    Mostly useful in structs.

        >>> t = Tell()
        >>> t
        Tell()
        >>> t.build(None)
        b''
        >>> stream = BytesIO(b'foobar')
        >>> stream.seek(3)
        3
        >>> t.parse_stream(stream)
        3
        >>> t.sizeof()
        0

        >>> class Example(Struct):
        ...     key = Bytes(3)
        ...     pos1 = Tell()
        ...     value = Bytes(3)
        ...     pos2 = Tell()
        >>> example = Example()
        >>> example.parse(b'foobar') == {
        ...     'key': b'foo', 'pos1': 3, 'value': b'bar', 'pos2': 6
        ... }
        True

    """
    __slots__ = Construct.__slots__

    def _build_stream(self, obj, stream, context):
        return stream.tell()

    def _parse_stream(self, stream, context):
        return stream.tell()

    def _sizeof(self, context):
        return 0

    def _repr(self):
        return 'Tell()'


class Checksum(Subconstruct):
    r"""
    Build and parse a checksum of data using a given ``hashlib``-compatible
    hash function.

        >>> import hashlib
        >>> c = Checksum(Bytes(32), hashlib.sha256, lambda ctx: ctx['data'])
        >>> c.build(None, context={'data': b'foo'})
        b',&\xb4kh\xff\xc6\x8f\xf9\x9bE<\x1d0A4\x13B-pd\x83\xbf\xa0\xf9\x8a^\x88bf\xe7\xae'
        >>> c.parse(_, context={'data': b'foo'})
        b',&\xb4kh\xff\xc6\x8f\xf9\x9bE<\x1d0A4\x13B-pd\x83\xbf\xa0\xf9\x8a^\x88bf\xe7\xae'
        >>> c.sizeof()
        32

    """
    __slots__ = Subconstruct.__slots__ + ('hash_func', 'data_func')

    def __init__(self, construct, hash_func, data_func):
        super().__init__(construct)
        self.hash_func = hash_func
        self.data_func = data_func

    def _build_stream(self, obj, stream, context):
        data = self.data_func(context)
        digest = self.hash_func(data).digest()
        if obj is None:
            obj = digest
        elif obj != digest:
            raise BuildingError(
                'wrong checksum, provided {!r} but expected {!r}'.format(
                    hexlify(obj), hexlify(digest),
                )
            )
        self.construct._build_stream(obj, stream, context)
        return obj

    def _parse_stream(self, stream, context):
        parsed_hash = self.construct._parse_stream(stream, context)
        data = self.data_func(context)
        expected_hash = self.hash_func(data).digest()
        if parsed_hash != expected_hash:
            raise ParsingError(
                'wrong checksum, parsed {!r} but expected {!r}'.format(
                    hexlify(parsed_hash), hexlify(expected_hash),
                )
            )
        return parsed_hash

    def _repr(self):
        return 'Checksum({}, hash_func={}, data_func={!r})'.format(
            self.construct, self.hash_func, self.data_func,
        )


# Debugging utilities
class Debug(Subconstruct):
    r"""
    In case of an error, launch a pdb-compatible debugger.

    """
    __slots__ = Subconstruct.__slots__ + ('debugger', 'on_exc')

    def __init__(self, construct, debugger=pdb, on_exc=Exception):
        super().__init__(construct)
        self.debugger = debugger
        self.on_exc = on_exc

    def _build_stream(self, obj, stream, context):
        try:
            super()._build_stream(obj, stream, context)
        except self.on_exc:
            pdb.post_mortem(sys.exc_info()[2])

    def _parse_stream(self, stream, context):
        try:
            super()._parse_stream(stream, context)
        except self.on_exc:
            pdb.post_mortem(sys.exc_info()[2])

    def _sizeof(self, context):
        try:
            super()._sizeof(context)
        except self.on_exc:
            pdb.post_mortem(sys.exc_info()[2])

    def _repr(self):
        return 'Debug({}, debugger={}, on_exc={})'.format(
            self.construct, self.debugger, self.on_exc
        )
