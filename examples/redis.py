from structures import (
    Line, Adapted, Struct, If, Contextual, Bytes, Const,
    RepeatExactly, Switch,
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
    data = If(lambda ctx: ctx['length'] != -1,
        Contextual(Bytes, lambda ctx: ctx['length']),
    )
    ending = If(lambda ctx: ctx['length'] != -1, Const(b'\r\n'))

bulk_string = Adapted(BulkString(), from_python, to_python)


class Array(Struct):
    length = integer
    data = If(lambda ctx: ctx['length'] != -1,
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
