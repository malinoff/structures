r"""
Implementation of RESP - Redis Serialization Protocol.
The spec is here: https://redis.io/topics/protocol

Currently only RESP types are implemented.

Simple strings:

    >>> message.parse(b'+OK\r\n')
    'OK'
    >>> message.build('OK')
    b'+OK\r\n'

Errors:

    >>> message.parse(b'-Error message\r\n')
    RedisError('Error message'...)
    >>> message.parse(b"-ERR unknown command 'foobar'\r\n")
    RedisError("ERR unknown command 'foobar'"...)
    >>> message.build(RedisError('an error'))
    b'-an error\r\n'

Integers:

    >>> message.parse(b':1000\r\n')
    1000
    >>> message.parse(b':-2\r\n')
    -2
    >>> message.build(123)
    b':123\r\n'

Bulk strings:

    >>> message.parse(b'$6\r\nfoobar\r\n')
    b'foobar'
    >>> message.parse(b'$0\r\n\r\n')
    b''
    >>> message.parse(b'$-1\r\n') is None
    True
    >>> message.build(b'xx\r\nyy')
    b'$6\r\nxx\r\nyy\r\n'

Arrays:

    >>> message.parse(b'*0\r\n')
    []
    >>> message.parse(b'*2\r\n$3\r\nfoo\r\n$3\r\nbar\r\n')
    [b'foo', b'bar']
    >>> message.parse(b'*3\r\n:1\r\n:2\r\n:3\r\n')
    [1, 2, 3]
    >>> message.parse(b'*5\r\n:1\r\n:2\r\n:3\r\n:4\r\n$6\r\nfoobar\r\n')
    [1, 2, 3, 4, b'foobar']
    >>> message.parse(b'*-1\r\n') is None
    True
    >>> message.parse(b'*2\r\n*3\r\n:1\r\n:2\r\n:3\r\n*2\r\n+Foo\r\n-Bar\r\n')
    [[1, 2, 3], ['Foo', RedisError('Bar'...)]]
    >>> message.parse(b'*3\r\n$3\r\nfoo\r\n$-1\r\n$3\r\nbar\r\n')
    [b'foo', None, b'bar']

"""

from structures import (
    Line, Adapted, Struct, If, Contextual, Bytes, Const, RepeatExactly, Switch,
)


def from_python(obj):
    if obj is None:
        return {'length': -1}
    return {'length': len(obj), 'data': obj}


def to_python(obj):
    if obj['length'] == -1:
        return None
    return obj['data']


simple_string = Line()


class RedisError(Exception):
    pass


error = Adapted(
    Line(),
    before_build=lambda obj: str(obj),
    after_parse=lambda obj: RedisError(obj),
)

integer = Adapted(Line(), before_build=str, after_parse=int)


class BulkString(Struct):
    length = integer  # note we can reuse existing definitions
    data = If(
        lambda ctx: ctx['length'] != -1,
        Contextual(Bytes, lambda ctx: ctx['length']),
    )
    ending = If(lambda ctx: ctx['length'] != -1, Const(b'\r\n'))


bulk_string = Adapted(BulkString(), from_python, to_python)


class Array(Struct):
    length = integer
    data = If(
        lambda ctx: ctx['length'] != -1,
        Contextual(
            RepeatExactly,
            construct=lambda ctx: message,
            n=lambda ctx: ctx['length'],
        )
    )


array = Adapted(Array(), from_python, to_python)


class Message(Struct):
    data_type = Bytes(1)
    data = Switch(lambda ctx: ctx['data_type'], cases={
        b'+': simple_string,
        b'-': error,
        b':': integer,
        b'$': bulk_string,
        b'*': array,
    })


def message_from_python(obj):
    if isinstance(obj, str):
        if '\r\n' not in obj:
            data_type = b'+'
        else:
            data_type = b'$'
            obj = obj.encode('utf-8')
    elif isinstance(obj, RedisError):
        data_type = b'-'
    elif isinstance(obj, int):
        data_type = b':'
    elif isinstance(obj, bytes):
        data_type = b'$'
    elif isinstance(obj, (list, tuple)):
        data_type = b'*'
    else:
        raise ValueError('unsupported type {}'.format(type(obj)))
    return {'data_type': data_type, 'data': obj}


message = Adapted(Message(), message_from_python, lambda obj: obj['data'])
