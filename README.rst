============================================================
``structures``: declarative binary data building and parsing
============================================================

.. image:: https://travis-ci.org/malinoff/structures.svg?branch=master
   :target: https://travis-ci.org/malinoff/structures
   :alt: CI Status

Have you ever tried to implement a parser of a network protocol or a file format?
This work can be tedious, especially when you need to translate declarative descriptions from RFC to completely imperative (often ``struct .pack``/``struct.unpack``) calls.
But what if you also need to build bytes according to the spec?
Maybe you're learning network protocols and just want to get stuff done?

Then ``structures`` may come in handy: it helps you to describe a protocol or a format *declaratively* and use the same definition for building and parsing binary data.
It supports sophisticated, context-dependent building and parsing and is **blazingly** fast (compared to alternatives).

One example is worth a thousand words - let's describe the foundation of RESP, Redis Serialization Protocol: types.
RESP is tiny and simply enough to feet into README format, but complex enought to show ``structures`` strengths.
It may be useful to keep  `RESP specification <https://redis.io/topics/protocol>`_ opened in your browser if you are not familiar with RESP.

Let's import all constructs we will use and define a few functions to convert from/to python objects:

.. code-block:: pycon

    >>> from structures import (
    ...     Line, Adapted, Struct, If, Contextual, Bytes, Const,
    ...     RepeatExactly, Switch,
    ... )
    >>> def from_python(obj):
    ...     if obj is None:
    ...         return {'length': -1}
    ...     return {'length': len(obj), 'data': obj}
    >>> def to_python(obj):
    ...     if obj['length'] == -1:
    ...         return None
    ...     return obj['data']

We are ready to declare Simple Strings.
Quoting the spec, RESP Simple Strings are encoded in the following way: a plus character, followed by a string that cannot contain a CR or LF character (no newlines are allowed), terminated by CRLF (that is "\r\n").
Except for a plus character, this is exactly how ``Line`` construct works, so let's simply use it:

.. code-block:: pycon

    >>> simple_string = Line()
    >>> simple_string.parse(b'OK\r\n')
    'OK'
    >>> simple_string.build('OK')
    b'OK\r\n'

A plus character will be defined later.

Next, Errors. A minus character will be defined later, just like a plus character.
An Error, except for the first character, is defined exactly like a Simple String.
However, we would like to follow python errors semantics and define a custom exception class.

.. code-block:: pycon

    >>> class RedisError(Exception): pass
    >>> error = Adapted(
    ...     Line(),
    ...     before_build=lambda obj: str(obj),
    ...     after_parse=lambda obj: RedisError(obj),
    ... )
    >>> error.parse(b'Error message\r\n')
    RedisError('Error message'...)
    >>> error.parse(b"ERR unknown command 'foobar'\r\n")
    RedisError("ERR unknown command 'foobar'"...)
    >>> error.build(RedisError('an error'))
    b'an error\r\n'

Next, Integers.

.. code-block:: pycon

    >>> integer = Adapted(Line(), before_build=str, after_parse=int)
    >>> integer.parse(b'100\r\n')
    100
    >>> integer.build(123)
    b'123\r\n'

Since RESP Integers are just string representations of integers, we need to adapt object to build and parsed object with ``str`` and ``int`` functions.
It is possible to specify ``str`` and ``int`` functions directly, without defining lambdas or custom functions because ``before_build`` and ``after_parse`` are functions of exactly one argument.

Next, Bulk Strings.
Quoting the spec, Bulk Strings are encoded in the following way:

 * A "$" byte followed by the number of bytes composing the string (a prefixed length), terminated by CRLF.
 * The actual string data.
 * A final CRLF.

Also a null value (``None``) must be represented by specifying length as -1.

.. code-block:: pycon

    >>> class BulkString(Struct):
    ...     length = integer  # note we can reuse existing definitions
    ...     data = If(lambda ctx: ctx['length'] != -1,
    ...         Contextual(Bytes, lambda ctx: ctx['length']),
    ...     )
    ...     ending = If(lambda ctx: ctx['length'] != -1, Const(b'\r\n'))
    >>> bulk_string = Adapted(BulkString(), from_python, to_python)
    >>> bulk_string.parse(b'6\r\nfoobar\r\n')
    b'foobar'
    >>> bulk_string.parse(b'0\r\n\r\n')
    b''
    >>> bulk_string.parse(b'-1\r\n')
    >>> bulk_string.build(b'xx\r\nyy')
    b'6\r\nxx\r\nyy\r\n'

Only one left! Meet Arrays.
Quoting the spec, RESP Arrays are sent using the following format:

 * A * character as the first byte, followed by the number of elements in the array as a decimal number, followed by CRLF.
 * An additional RESP type for every element of the Array.

Like Bulk Strings, a null (``None``) arrays must be supported.

.. code-block:: pycon

    >>> class Array(Struct):
    ...     length = integer
    ...     data = If(lambda ctx: ctx['length'] != -1,
    ...         Contextual(
    ...             RepeatExactly,
    ...             construct=lambda ctx: message,
    ...             n=lambda ctx: ctx['length'],
    ...         ),
    ...     )
    >>> array = Adapted(Array(), from_python, to_python)

Note that we referenced a not yet defined ``message`` variable. Let's define it!
It will finally build/parse RESP type characters and pick up a correct type:

.. code-block:: pycon

    >>> class Message(Struct):
    ...     data_type = Bytes(1)
    ...     data = Switch(lambda ctx: ctx['data_type'], cases={
    ...         b'+': simple_string,
    ...         b'-': error,
    ...         b':': integer,
    ...         b'$': bulk_string,
    ...         b'*': array,
    ...     })
    >>> def message_from_python(obj):
    ...     if isinstance(obj, str):
    ...         if '\r\n' not in obj:
    ...             data_type = b'+'
    ...         else:
    ...             data_type = b'$'
    ...             obj = obj.encode('utf-8')
    ...     elif isinstance(obj, RedisError):
    ...         data_type = b'-'
    ...     elif isinstance(obj, int):
    ...         data_type = b':'
    ...     elif isinstance(obj, bytes):
    ...         data_type = b'$'
    ...     elif isinstance(obj, (list, tuple)):
    ...         data_type = b'*'
    ...     else:
    ...         raise ValueError('unsupported type {}'.format(type(obj)))
    ...     return {'data_type': data_type, 'data': obj}
    >>> message = Adapted(Message(), message_from_python, lambda obj: obj['data'])

This is how you can define recursive structures, or structures that depend on each other.

Now we can finally ensure the correctness of ``array``:

.. code-block:: pycon

    >>> array.parse(b'0\r\n')
    []
    >>> array.parse(b'2\r\n$3\r\nfoo\r\n$3\r\nbar\r\n')
    [b'foo', b'bar']
    >>> array.parse(b'3\r\n:1\r\n:2\r\n:3\r\n')
    [1, 2, 3]
    >>> array.parse(b'5\r\n:1\r\n:2\r\n:3\r\n:4\r\n$6\r\nfoobar\r\n')
    [1, 2, 3, 4, b'foobar']
    >>> array.parse(b'-1\r\n')

And the correctness of all types:

.. code-block:: pycon

    >>> message.parse(b'+OK\r\n')  # simple string
    'OK'
    >>> message.parse(b'-Error message\r\n')  # error
    RedisError('Error message'...)
    >>> message.parse(b':1000\r\n')  # integer
    1000
    >>> message.parse(b'$6\r\nfoobar\r\n')  # bulk string
    b'foobar'
    >>> message.parse(b'*2\r\n*3\r\n:1\r\n:2\r\n:3\r\n*2\r\n+Foo\r\n-Bar\r\n')  # complex array
    [[1, 2, 3], ['Foo', RedisError('Bar'...)]]
    >>> message.parse(b'*3\r\n$3\r\nfoo\r\n$-1\r\n$3\r\nbar\r\n')
    [b'foo', None, b'bar']

A complete module can be found in `<examples/redis.py>`_.
