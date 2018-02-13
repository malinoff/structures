==================================================
``structures``: declarative binary data processing
==================================================

.. image:: https://travis-ci.org/malinoff/structures.svg?branch=master
   :target: https://travis-ci.org/malinoff/structures
   :alt: CI Status

``structures`` is a Python package that allows you to declaratively describe binary data structures (like a network protocol or a file format), and to use that declaration to process binary data: to build bytes from python objects, to parse bytes to python objects and to calculate size of the described structure.

.. code-block:: pycon

    >>> from structures import Struct, Const, Integer, Contextual, RepeatExactly, Bytes
    >>> class BMP(Struct):
    ...     signature = Const(b"BMP")  # 3 constant bytes
    ...     width = Integer(1)  # 1 byte
    ...     height = Integer(1)  # 1 byte
    ...     pixels = Contextual(Bytes, lambda ctx: ctx['width'] * ctx['height'])  #  width * height bytes
    >>> bmp = BMP()
    >>> bmp.build({'width': 3, 'height': 2, 'pixels': b'\x07\x08\t\x0b\x0c\r'})
    b'BMP\x03\x02\x07\x08\t\x0b\x0c\r'
    >>> bmp.parse(b'BMP\x03\x02\x07\x08\t\x0b\x0c\r') == {
    ...     'signature': b'BMP', 'width': 3, 'height': 2,
    ...     'pixels': b'\x07\x08\t\x0b\x0c\r',
    ... }
    True
    >>> bmp.sizeof(context={'width': 10, 'height': 10})
    105

More sophisticated, real-world examples live in `examples <https://github.com/malinoff/structures>`_ directory.

Available Constructs
--------------------

* Primitive: Pass, Flag, Bytes, Integer, Float, Padding, Const
* Adapters: Repeat, RepeatExactly, Adapted, Prefixed, Padded, Aligned
* Strings: String, PascalString, CString, Line
* Structs: Struct, Contextual, Computed
* Bit-wise: BitFields
* Conditionals: If, Switch, Enum, Raise
* Stream manipulation: Offset, Tell
* Data transformers: Checksum
* Debugging utilities: Debug

You can find usage examples in constructs docstrings.

All docstrings, examples, and even this readme are tested using doctest.

How To Contribute
-----------------

This project uses Pull Requests for all kinds of contributions.

You have a question? Make a pull request with an example of structure that confuses you.
This way we will improve the docs and examples so another person won't be confused.
And they won't need to dig through issues to see if their question has already been answered.

You think you have found a bug? Make a pull request describing a buggy structure.
If you are courage enough, feel free to also submit a bug fix :)

You have a feature request? Make a pull request briefly describing your feature.
This can be a class with a (failing) example in its docstring.
Even if it's not valid python code - your example will help to understand the intention.
Having an initial implementation of your feature will greatly reduce the time needed to make your feature appear in the next release.

A detailed guide on how to contribute can be found in `CONTRIBUTING.rst <https://github.com/malinoff/structures/blob/master/CONTRIBUTING.rst>`_.
